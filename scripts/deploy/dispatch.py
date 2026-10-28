"""Send an immutable release to the one configured EC2 instance and await its result."""

import argparse
import json
import re
import subprocess
import time


def aws(*args):
    return json.loads(
        subprocess.check_output(
            ["aws", *args, "--output", "json", "--no-cli-pager"], text=True
        )
    )


def deploy(instance: str, sha: str):
    if not re.fullmatch(r"i-[0-9a-f]+", instance) or not re.fullmatch(
        r"[0-9a-f]{40}", sha
    ):
        raise ValueError("Invalid instance or commit")
    response = aws(
        "ssm",
        "send-command",
        "--instance-ids",
        instance,
        "--document-name",
        "AWS-RunShellScript",
        "--comment",
        f"ViaCRM deployment {sha}",
        "--timeout-seconds",
        "600",
        "--parameters",
        json.dumps(
            {
                "commands": [f"/opt/viacrm/bin/apply-release {sha}"],
                "executionTimeout": ["1800"],
            }
        ),
    )
    command_id = response["Command"]["CommandId"]
    print(f"SSM command: {command_id}", flush=True)
    for _ in range(240):
        time.sleep(5)
        # Invocation creation is eventually consistent. Do not hide later AWS errors.
        result = subprocess.run(
            [
                "aws",
                "ssm",
                "get-command-invocation",
                "--command-id",
                command_id,
                "--instance-id",
                instance,
                "--output",
                "json",
                "--no-cli-pager",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            if "InvocationDoesNotExist" in result.stderr:
                continue
            raise RuntimeError(result.stderr)
        invocation = json.loads(result.stdout)
        status = invocation["Status"]
        if status in {"Pending", "InProgress", "Delayed"}:
            continue
        print(invocation.get("StandardOutputContent", ""))
        if status != "Success":
            print(invocation.get("StandardErrorContent", ""))
            raise RuntimeError(f"Deployment failed: {status}")
        return
    raise TimeoutError(
        "Deployment has not completed; inspect the SSM command before retrying"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    deploy(args.instance, args.sha)
