"""Add backups, alarms and the Instagram bot image repository; refuse any other stack change.

Run with an operator's own AWS session (for example after `aws login`). The script creates a
CloudFormation change set from infra/aws/stack.json, reusing every existing parameter value, and
inspects it. It executes only with --execute and only when every change adds one of the expected
resources, apart from in-place (non-replacing) policy edits to DeployRole and HostRole. In particular it refuses when the production Host would be modified or
replaced, for example because the latest Amazon Linux AMI parameter now resolves differently.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STACK = "viacrm-production"
REGION = "ap-south-1"
EXPECTED_ADDS = {
    "BackupBucket",
    "BackupBucketPolicy",
    "HostBackupPolicy",
    "AlertTopic",
    "AlertEmailSubscription",
    "SiteDownAlarm",
    "BackupMissingAlarm",
    "DiskSpaceAlarm",
    "SystemStatusAlarm",
    "InstanceStatusAlarm",
    "IgbotRepository",
}
# In-place policy edits that add the Instagram bot's image repository; never a replacement.
ALLOWED_MODIFY = {"DeployRole", "HostRole"}
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def aws(*args):
    output = subprocess.run(
        ["aws", *args, "--region", REGION, "--output", "json"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(output) if output.strip() else {}


def unexpected_changes(changes, alert_email):
    """Return human-readable problems; an empty list means the change set is safe to run."""
    allowed = set(EXPECTED_ADDS)
    if not alert_email:
        allowed.discard("AlertEmailSubscription")
    problems = []
    for change in changes:
        item = change.get("ResourceChange", {})
        logical = item.get("LogicalResourceId", "?")
        action = item.get("Action")
        in_place = action == "Modify" and logical in ALLOWED_MODIFY and item.get("Replacement") == "False"
        if in_place:
            continue
        if action != "Add" or logical not in allowed:
            problems.append(f"{action} {logical} (replacement: {item.get('Replacement', 'n/a')})")
    missing = allowed - {c.get("ResourceChange", {}).get("LogicalResourceId") for c in changes}
    problems += [f"expected new resource {name} is missing" for name in sorted(missing)]
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alert-email", default="", help="Email for alarms (AWS sends a confirmation)")
    parser.add_argument("--execute", action="store_true", help="Run the change set after it passes checks")
    args = parser.parse_args()
    if args.alert_email and not EMAIL.fullmatch(args.alert_email):
        parser.error("Enter a valid alert email")
    stack = aws("cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"][0]
    if stack["StackStatus"] not in {"CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"}:
        sys.exit(f"Stack is {stack['StackStatus']}; wait until it is stable")
    existing = {p["ParameterKey"] for p in stack.get("Parameters", [])}
    # Pin the AMI to the image the running server already uses, so the Host is unchanged.
    host = aws("cloudformation", "describe-stack-resource", "--stack-name", STACK, "--logical-resource-id", "Host")
    instance = host["StackResourceDetail"]["PhysicalResourceId"]
    image = aws("ec2", "describe-instances", "--instance-ids", instance)["Reservations"][0]["Instances"][0]["ImageId"]
    print(f"Pinning AmiId to {image}, the image of running instance {instance}")
    parameters = [
        f"ParameterKey={key},UsePreviousValue=true" for key in sorted(existing) if key not in {"AlertEmail", "AmiId"}
    ]
    parameters.append(f"ParameterKey=AmiId,ParameterValue={image}")
    parameters.append(f"ParameterKey=AlertEmail,ParameterValue={args.alert_email}")
    name = "add-backups-monitoring-" + time.strftime("%Y%m%d%H%M%S", time.gmtime())
    aws(
        "cloudformation",
        "create-change-set",
        "--stack-name",
        STACK,
        "--change-set-name",
        name,
        "--change-set-type",
        "UPDATE",
        "--capabilities",
        "CAPABILITY_IAM",
        "--template-body",
        "file://" + str(ROOT / "infra/aws/stack.json"),
        "--parameters",
        *parameters,
    )
    subprocess.run(
        ["aws", "cloudformation", "wait", "change-set-create-complete", "--stack-name", STACK,
         "--change-set-name", name, "--region", REGION],
        check=False,
    )
    described = aws("cloudformation", "describe-change-set", "--stack-name", STACK, "--change-set-name", name)
    changes = described.get("Changes", [])
    for change in changes:
        item = change["ResourceChange"]
        print(f"{item['Action']:8} {item['LogicalResourceId']:28} {item['ResourceType']}")
    problems = unexpected_changes(changes, args.alert_email)
    if described.get("Status") != "CREATE_COMPLETE" or problems:
        print("Refusing to execute:", described.get("StatusReason", ""), *problems, sep="\n  ")
        aws("cloudformation", "delete-change-set", "--stack-name", STACK, "--change-set-name", name)
        sys.exit(1)
    if not args.execute:
        print(f"Change set {name} adds only the expected resources. Re-run with --execute to apply.")
        aws("cloudformation", "delete-change-set", "--stack-name", STACK, "--change-set-name", name)
        return
    aws("cloudformation", "execute-change-set", "--stack-name", STACK, "--change-set-name", name)
    subprocess.run(
        ["aws", "cloudformation", "wait", "stack-update-complete", "--stack-name", STACK, "--region", REGION],
        check=True,
    )
    outputs = {o["OutputKey"]: o["OutputValue"] for o in aws(
        "cloudformation", "describe-stacks", "--stack-name", STACK)["Stacks"][0]["Outputs"]}
    print("Applied. Backup bucket:", outputs.get("BackupBucket"), "Alert topic:", outputs.get("AlertTopic"))


if __name__ == "__main__":
    main()
