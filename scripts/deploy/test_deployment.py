import importlib.util
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class ProductionConfiguration(unittest.TestCase):
    def test_secrets_are_private_stable_and_not_development_credentials(self):
        configure = module("host_config").configure
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configure(root, "203.0.113.10")
            first = (root / "shared/app.env").read_bytes()
            configure(root, "203.0.113.10")
            self.assertEqual(first, (root / "shared/app.env").read_bytes())
            self.assertEqual((root / "shared/app.env").stat().st_mode & 0o777, 0o600)
            values = {
                k: json.loads(v)
                for k, v in (line.split("=", 1) for line in first.decode().splitlines())
            }
            self.assertEqual(values["ENVIRONMENT"], "production")
            self.assertEqual(values["PUBLIC_ORIGIN"], "https://203.0.113.10")
            self.assertGreaterEqual(len(values["SECRET_KEY"]), 40)
            self.assertNotIn("development", values["SECRET_KEY"])
            self.assertIn("@db:5432/talkocrm", values["DATABASE_URL"])

    def test_incomplete_environment_is_never_rekeyed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "shared").mkdir()
            (root / "shared/app.env").write_text("existing-encryption-key")
            with self.assertRaises(RuntimeError):
                module("host_config").configure(root, "crm.example.com")
            self.assertEqual(
                (root / "shared/app.env").read_text(), "existing-encryption-key"
            )

    def test_untrusted_host_cannot_inject_environment(self):
        for host in [
            "https://crm.example.com",
            "crm.example.com\nSECRET_KEY=bad",
            "$(touch bad)",
            "a/b",
        ]:
            with (
                self.subTest(host=host),
                tempfile.TemporaryDirectory() as directory,
                self.assertRaises(ValueError),
            ):
                module("host_config").configure(Path(directory), host)


class ReleasePackaging(unittest.TestCase):
    def test_archive_has_only_deployment_files_and_immutable_references(self):
        images = {
            f"{name}_IMAGE": f"example.com/viacrm/{name.lower()}@sha256:" + "b" * 64
            for name in ["API", "WEB", "POSTGRES", "CADDY"]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release.tar.gz"
            module("package_release").package(path, "a" * 40, images)
            with tarfile.open(path) as archive:
                self.assertEqual(
                    set(archive.getnames()),
                    {
                        "compose.yaml",
                        "Caddyfile",
                        "deploy.sh",
                        "host_config.py",
                        "cleanup_images.py",
                        "images.env",
                    },
                )
                env = archive.extractfile("images.env").read().decode()
                self.assertIn("RELEASE_SHA=" + "a" * 40, env)
                self.assertNotIn("SECRET_KEY", env)
                self.assertNotIn("DB_PASSWORD", env)
                self.assertTrue(all(member.isfile() for member in archive.getmembers()))

    def test_mutable_images_and_invalid_commits_are_rejected(self):
        package = module("package_release").package
        with self.assertRaises(ValueError):
            package(Path("unused"), "main", {})
        with self.assertRaises(ValueError):
            package(Path("unused"), "a" * 40, {"API_IMAGE": "example.com/api:latest"})


class Cleanup(unittest.TestCase):
    def test_current_and_previous_images_survive_and_no_force_or_volume_deletion(self):
        cleanup_module = module("cleanup_images")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for release in ["current", "previous"]:
                (root / release).mkdir()
                (root / release / "images.env").write_text(
                    f"API_IMAGE={release}-api\nWEB_IMAGE={release}-web\n"
                )

            def output(command, **kwargs):
                if command[2] == "inspect":
                    return "sha256:" + command[-1] + "\n"
                return "sha256:current-api\nsha256:current-web\nsha256:previous-api\nsha256:previous-web\nsha256:obsolete\nsha256:obsolete"

            with (
                patch.object(
                    cleanup_module.subprocess, "check_output", side_effect=output
                ),
                patch.object(cleanup_module.subprocess, "run") as run,
            ):
                cleanup_module.cleanup(root)
            run.assert_called_once_with(
                ["docker", "image", "rm", "sha256:obsolete"], check=False
            )


class Infrastructure(unittest.TestCase):
    def test_ci_is_main_only_and_database_is_private_and_retained(self):
        config = module("aws_template").template()
        role = config["Resources"]["DeployRole"]["Properties"]
        trust = role["AssumeRolePolicyDocument"]["Statement"][0]
        self.assertEqual(
            trust["Condition"]["StringEquals"][
                "token.actions.githubusercontent.com:sub"
            ],
            {"Fn::Sub": "${GitHubSubjectPrefix}:ref:refs/heads/main"},
        )
        host = config["Resources"]["Host"]
        self.assertEqual(host["DeletionPolicy"], "Retain")
        self.assertTrue(
            host["Properties"]["BlockDeviceMappings"][0]["Ebs"]["Encrypted"]
        )
        self.assertEqual(
            host["Properties"]["MetadataOptions"]["HttpTokens"], "required"
        )
        ingress = config["Resources"]["SecurityGroup"]["Properties"][
            "SecurityGroupIngress"
        ]
        self.assertEqual({rule["FromPort"] for rule in ingress}, {80, 443})


if __name__ == "__main__":
    unittest.main()
