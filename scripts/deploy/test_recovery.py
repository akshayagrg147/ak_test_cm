"""Off-server backup, health reporting and alarm configuration, using fake docker/aws commands."""

import importlib.util
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCOUNT = "123456789012"
FAKES = {
    "docker": r"""#!/bin/bash
echo "docker $*" >> "$LOG"
if [[ "$*" == *pg_dump* ]]; then printf 'PGDMP-fake-dump'; exit 0; fi
if [[ "$1 $2" == "volume inspect" ]]; then [[ -n "${IGBOT_VOLUME:-}" ]]; exit; fi
if [[ "$1" == run ]]; then
    all="$*"
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == -v && "$2" == *:/backup ]]; then target="${2%:/backup}"; fi
        shift
    done
    if [[ "$all" == *viacrm_igbot_data* ]]; then printf 'bot' > "$target/igbot-data.tar.gz"
    else printf 'files' > "$target/files.tar.gz"; fi
fi
""",
    "aws": r"""#!/bin/bash
echo "aws $*" >> "$LOG"
if [[ "$1 $2" == "sts get-caller-identity" ]]; then echo "$ACCOUNT"; exit 0; fi
if [[ "$1 $2" == "s3api put-object" && -n "${FAIL_UPLOAD:-}" ]]; then echo 'upload failed' >&2; exit 1; fi
if [[ "$1" == s3 ]]; then echo 'aws s3 high-level commands lack --expected-bucket-owner on the host CLI' >&2; exit 255; fi
""",
    "flock": "#!/bin/bash\nexit 0\n",
    "curl": '#!/bin/bash\necho "curl $*" >> "$LOG"\nprintf \'%s\' "$HEALTH_BODY"\n',
    "df": "#!/bin/bash\nprintf 'Use%%\\n 42%%\\n'\n",
}


def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class HostScripts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "viacrm"
        bin_dir = Path(self.temporary.name) / "bin"
        bin_dir.mkdir()
        for name, body in FAKES.items():
            path = bin_dir / name
            path.write_text(body)
            path.chmod(path.stat().st_mode | stat.S_IEXEC)
        release = self.root / "releases" / ("a" * 40)
        release.mkdir(parents=True)
        (release / "images.env").write_text("POSTGRES_IMAGE=postgres@sha256:" + "c" * 64 + "\n")
        (release / "compose.yaml").write_text("services: {}\n")
        (self.root / "current").symlink_to(release)
        (self.root / "shared").mkdir()
        (self.root / "backups").mkdir()
        (self.root / "shared/host.env").write_text("AWS_REGION=ap-south-1\nPUBLIC_HOST=viacrm.in\n")
        (self.root / "shared/app.env").write_text("SECRET_KEY=x\n")
        (self.root / "shared/database.env").write_text("POSTGRES_PASSWORD=y\n")
        self.log = Path(self.temporary.name) / "commands.log"
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "DEPLOY_ROOT": str(self.root),
            "LOG": str(self.log),
            "ACCOUNT": ACCOUNT,
        }

    def tearDown(self):
        self.temporary.cleanup()

    def run_script(self, name, *args, **env):
        return subprocess.run(
            ["bash", str(HERE / name), *args],
            env={**self.env, **env},
            capture_output=True,
            text=True,
            timeout=60,
        )

    def commands(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_daily_backup_uploads_encrypted_copy_with_manifest_and_reports_success(self):
        result = self.run_script("backup.sh", "daily")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        [folder] = list((self.root / "backups").glob("daily-*"))
        manifest = json.loads((folder / "manifest.json").read_text())
        self.assertEqual(
            set(manifest["files"]), {"database.dump", "files.tar.gz", "app.env", "database.env", "release.txt"}
        )
        self.assertEqual(manifest["files"]["database.dump"]["bytes"], len("PGDMP-fake-dump"))
        self.assertTrue((folder / ".uploaded").exists())
        self.assertEqual((folder / "release.txt").read_text().strip(), "a" * 40)
        uploads = [c for c in self.commands() if c.startswith("aws s3api put-object")]
        keys = {c.split("--key ")[1].split()[0] for c in uploads}
        self.assertEqual(keys, {f"daily/{folder.name}/{name}" for name in manifest["files"]} | {f"daily/{folder.name}/manifest.json"})
        for upload in uploads:
            self.assertIn(f"--bucket viacrm-backups-{ACCOUNT}-ap-south-1", upload)
            self.assertIn("--server-side-encryption AES256", upload)
            self.assertIn(f"--expected-bucket-owner {ACCOUNT}", upload)
        self.assertFalse((folder / ".uploaded").name in " ".join(keys))
        metrics = [c for c in self.commands() if "put-metric-data" in c]
        self.assertTrue(any("--metric-name BackupSucceeded --value 1" in c for c in metrics))
        self.assertTrue(all("--namespace ViaCRM" in c for c in metrics))
        dump = next(c for c in self.commands() if "pg_dump" in c)
        self.assertIn("--project-name viacrm", dump)
        # Online backup: the CRM is never stopped for the daily copy.
        self.assertFalse(any(" stop " in c for c in self.commands()))

    def test_instagram_bot_data_and_settings_are_backed_up_when_present(self):
        (self.root / "shared/igbot.env").write_text("APP_SECRET=z\n")
        result = self.run_script("backup.sh", "daily", IGBOT_VOLUME="1")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        [folder] = list((self.root / "backups").glob("daily-*"))
        files = json.loads((folder / "manifest.json").read_text())["files"]
        self.assertIn("igbot-data.tar.gz", files)
        self.assertIn("igbot.env", files)
        self.assertEqual((folder / "igbot.env").stat().st_mode & 0o777, 0o600)

    def test_failed_upload_keeps_local_copy_and_reports_no_success(self):
        result = self.run_script("backup.sh", "daily", FAIL_UPLOAD="1")
        self.assertNotEqual(result.returncode, 0)
        [folder] = list((self.root / "backups").glob("daily-*"))
        self.assertTrue((folder / "database.dump").exists())
        self.assertFalse((folder / ".uploaded").exists())
        self.assertFalse(any("BackupSucceeded" in c for c in self.commands()))

    def test_empty_database_dump_is_never_uploaded(self):
        folder = self.root / "backups" / ("20261111T000000Z-" + "a" * 40)
        folder.mkdir()
        (folder / "database.dump").write_text("")
        result = self.run_script("backup.sh", "upload", str(folder))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing or empty", result.stderr + result.stdout)
        self.assertFalse(any(c.startswith("aws s3api put-object") for c in self.commands()))

    def test_release_upload_and_local_pruning_only_remove_uploaded_old_copies(self):
        backups = self.root / "backups"
        names = [f"2026110{day}T000000Z-" + "b" * 40 for day in range(1, 9)]
        for index, name in enumerate(names):
            (backups / name).mkdir()
            (backups / name / "database.dump").write_text("dump")
            if index != 0:
                (backups / name / ".uploaded").touch()
        newest = backups / names[-1]
        (newest / ".uploaded").unlink()
        result = self.run_script("backup.sh", "upload", str(newest), BACKUP_BUCKET="named-bucket")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        upload = next(c for c in self.commands() if c.startswith("aws s3api put-object"))
        self.assertIn("--bucket named-bucket", upload)
        self.assertIn(f"--key release/{newest.name}/", upload)
        remaining = sorted(p.name for p in backups.iterdir())
        # Five newest kept; the oldest never-uploaded copy is kept too.
        self.assertEqual(remaining, sorted([names[0], *names[-5:]]))

    def test_monitor_reports_health_and_disk(self):
        healthy = json.dumps({"status": "ok", "database": "ok", "worker": "ok"})
        result = self.run_script("monitor.sh", HEALTH_BODY=healthy)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = next(c for c in self.commands() if "put-metric-data" in c)
        self.assertIn("MetricName=HealthOK,Value=1", report)
        self.assertIn("MetricName=DiskUsedPercent,Value=42", report)
        self.assertIn("https://viacrm.in/api/health", next(c for c in self.commands() if c.startswith("curl")))
        self.assertNotIn("--insecure", self.log.read_text())
        self.log.unlink()
        for body in [json.dumps({"status": "degraded", "database": "ok", "worker": "offline"}), "", "<html>"]:
            self.run_script("monitor.sh", HEALTH_BODY=body)
        reports = [c for c in self.commands() if "put-metric-data" in c]
        self.assertEqual(len(reports), 3)
        self.assertTrue(all("MetricName=HealthOK,Value=0" in c for c in reports))


class RecoveryInfrastructure(unittest.TestCase):
    def setUp(self):
        self.config = module("aws_template").template()
        self.resources = self.config["Resources"]

    def test_backup_bucket_is_private_encrypted_versioned_and_expires_old_copies(self):
        bucket = self.resources["BackupBucket"]
        self.assertEqual(bucket["DeletionPolicy"], "Retain")
        properties = bucket["Properties"]
        self.assertEqual(properties["VersioningConfiguration"]["Status"], "Enabled")
        self.assertTrue(all(properties["PublicAccessBlockConfiguration"].values()))
        rules = {r["Prefix"]: r for r in properties["LifecycleConfiguration"]["Rules"]}
        self.assertEqual(rules["daily/"]["ExpirationInDays"], 35)
        self.assertEqual(rules["release/"]["ExpirationInDays"], 90)
        deny = self.resources["BackupBucketPolicy"]["Properties"]["PolicyDocument"]["Statement"][0]
        self.assertEqual(deny["Condition"], {"Bool": {"aws:SecureTransport": "false"}})

    def test_server_can_only_upload_backups_and_publish_its_own_metrics(self):
        statements = self.resources["HostBackupPolicy"]["Properties"]["PolicyDocument"]["Statement"]
        actions = {s["Action"] for s in statements}
        self.assertEqual(actions, {"s3:PutObject", "cloudwatch:PutMetricData"})
        upload = next(s for s in statements if s["Action"] == "s3:PutObject")
        self.assertEqual(
            upload["Resource"],
            [{"Fn::Sub": "${BackupBucket.Arn}/daily/*"}, {"Fn::Sub": "${BackupBucket.Arn}/release/*"}],
        )
        metrics = next(s for s in statements if s["Action"] == "cloudwatch:PutMetricData")
        self.assertEqual(metrics["Condition"], {"StringEquals": {"cloudwatch:namespace": "ViaCRM"}})

    def test_alarms_notify_and_treat_missing_reports_as_failures(self):
        site = self.resources["SiteDownAlarm"]["Properties"]
        backup = self.resources["BackupMissingAlarm"]["Properties"]
        self.assertEqual((site["MetricName"], site["TreatMissingData"]), ("HealthOK", "breaching"))
        self.assertEqual((backup["MetricName"], backup["TreatMissingData"]), ("BackupSucceeded", "breaching"))
        self.assertEqual(backup["Period"] * backup["EvaluationPeriods"], 26 * 3600)
        system = self.resources["SystemStatusAlarm"]["Properties"]
        self.assertIn({"Fn::Sub": "arn:aws:automate:${AWS::Region}:ec2:recover"}, system["AlarmActions"])
        for name, resource in self.resources.items():
            if resource["Type"] == "AWS::CloudWatch::Alarm":
                self.assertIn({"Ref": "AlertTopic"}, resource["Properties"]["AlarmActions"], name)
                self.assertIn({"Ref": "AlertTopic"}, resource["Properties"]["OKActions"], name)
        self.assertEqual(self.resources["AlertEmailSubscription"]["Condition"], "HasAlertEmail")

    def test_recovery_changes_do_not_modify_the_running_server_or_existing_roles(self):
        committed = json.loads((HERE.parents[1] / "infra/aws/stack.json").read_text())
        self.assertEqual(committed, json.loads(json.dumps(self.config)))
        host = self.resources["Host"]["Properties"]
        user_data = json.dumps(host["UserData"])
        # Changing UserData would restart the instance; recovery uses release-installed timers.
        self.assertNotIn("BackupBucket", user_data)
        self.assertNotIn("viacrm-backup", user_data)
        host_role = json.dumps(self.resources["HostRole"])
        self.assertNotIn("BackupBucket", host_role)
        self.assertNotIn("cloudwatch", host_role)

    def test_instagram_bot_image_repository_matches_existing_repositories(self):
        repo = self.resources["IgbotRepository"]
        self.assertEqual(repo["Properties"]["RepositoryName"], "viacrm/igbot")
        self.assertEqual(repo["Properties"]["ImageTagMutability"], "IMMUTABLE")
        self.assertEqual(repo["DeletionPolicy"], "Retain")
        arn = {"Fn::Sub": "arn:aws:ecr:${AWS::Region}:${AWS::AccountId}:repository/viacrm/igbot"}
        host = self.resources["HostRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
        pull = next(s for s in host if isinstance(s.get("Resource"), list) and arn in s["Resource"])
        self.assertNotIn("ecr:PutImage", pull["Action"])
        deploy = self.resources["DeployRole"]["Properties"]["Policies"][0]["PolicyDocument"]["Statement"]
        push = next(s for s in deploy if isinstance(s.get("Resource"), list) and arn in s["Resource"])
        self.assertIn("ecr:PutImage", push["Action"])


class GuardedStackUpdate(unittest.TestCase):
    def change(self, logical, action="Add", replacement=None):
        item = {"LogicalResourceId": logical, "Action": action, "ResourceType": "X"}
        if replacement:
            item["Replacement"] = replacement
        return {"ResourceChange": item}

    def test_only_expected_additions_may_run(self):
        apply = module("apply_recovery_stack")
        adds = [self.change(name) for name in sorted(apply.EXPECTED_ADDS)]
        self.assertEqual(apply.unexpected_changes(adds, "owner@example.com"), [])
        without_email = [c for c in adds if c["ResourceChange"]["LogicalResourceId"] != "AlertEmailSubscription"]
        self.assertEqual(apply.unexpected_changes(without_email, ""), [])
        # A newer Amazon Linux AMI would modify or replace the production server: refuse.
        problems = apply.unexpected_changes([*adds, self.change("Host", "Modify", "True")], "owner@example.com")
        self.assertEqual(problems, ["Modify Host (replacement: True)"])
        # Adding the bot's image repository edits two role policies in place, never replacing them.
        in_place = [self.change("DeployRole", "Modify", "False"), self.change("HostRole", "Modify", "False")]
        self.assertEqual(apply.unexpected_changes([*adds, *in_place], "a@b.co"), [])
        self.assertTrue(apply.unexpected_changes([*adds, self.change("HostRole", "Modify")], "a@b.co"))
        self.assertTrue(apply.unexpected_changes([*adds, self.change("HostRole", "Modify", "True")], "a@b.co"))
        self.assertTrue(apply.unexpected_changes([*adds, self.change("Host", "Modify", "False")], "a@b.co"))
        self.assertIn(
            "expected new resource SiteDownAlarm is missing",
            apply.unexpected_changes([c for c in adds if "SiteDown" not in json.dumps(c)], "a@b.co"),
        )


if __name__ == "__main__":
    unittest.main()
