"""Configure the purchased ViaCRM domain through the existing scoped SSM role."""

import argparse
import json
import os
import re
import subprocess
import time

POLL_SECONDS = 22 * 60
AWS_TIMEOUT = 30


def aws(*arguments):
    try:
        result = subprocess.run(
            [
                "aws",
                *arguments,
                "--output",
                "json",
                "--no-cli-pager",
                "--cli-connect-timeout",
                "10",
                "--cli-read-timeout",
                "20",
            ],
            env={**os.environ, "AWS_MAX_ATTEMPTS": "1"},
            capture_output=True,
            text=True,
            check=False,
            timeout=AWS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(
            "SSM submission timed out; inspect recent commands before retrying"
        ) from None
    if result.returncode:
        raise RuntimeError(
            "SSM submission failed; inspect recent commands before retrying"
        )
    return json.loads(result.stdout)


def command(sha: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Expected the exact deployed Git commit")
    return f"""set -eu
python3 - '{sha}' <<'PY'
import pathlib
import subprocess
import sys

root = pathlib.Path('/opt/viacrm')
release = (root / 'current').resolve(strict=True)
if release.parent != root / 'releases' or release.name != sys.argv[1]:
    raise RuntimeError('The requested main commit must be deployed first')
subprocess.run([
    sys.executable, str(release / 'configure_domain.py'),
    '--host', 'viacrm.in',
    '--alias', 'www.viacrm.in', '--alias', '13.234.72.21',
    '--default-sni', '13.234.72.21',
    '--expected-release', sys.argv[1],
], check=True)
PY
"""


def configure(instance: str, sha: str):
    if not re.fullmatch(r"i-[0-9a-f]+", instance):
        raise ValueError("Invalid ViaCRM instance")
    shell = command(sha)
    response = aws(
        "ssm",
        "send-command",
        "--instance-ids",
        instance,
        "--document-name",
        "AWS-RunShellScript",
        "--comment",
        f"ViaCRM domain configuration {sha}",
        "--timeout-seconds",
        "600",
        "--parameters",
        json.dumps({"commands": [shell], "executionTimeout": ["1200"]}),
    )
    command_id = response["Command"]["CommandId"]
    print(f"SSM command: {command_id}", flush=True)
    deadline = time.monotonic() + POLL_SECONDS
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(5, remaining))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
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
                    "--cli-connect-timeout",
                    "10",
                    "--cli-read-timeout",
                    "20",
                ],
                env={**os.environ, "AWS_MAX_ATTEMPTS": "1"},
                capture_output=True,
                text=True,
                check=False,
                timeout=min(AWS_TIMEOUT, remaining),
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(
                "SSM status check timed out; inspect the command before retrying"
            ) from None
        if result.returncode:
            if "InvocationDoesNotExist" in result.stderr:
                continue
            raise RuntimeError(
                "Unable to read the SSM result; inspect the command before retrying"
            )
        invocation = json.loads(result.stdout)
        if invocation["Status"] in {"Pending", "InProgress", "Delayed"}:
            continue
        if invocation["Status"] != "Success":
            raise RuntimeError(f"Domain configuration failed: {invocation['Status']}")
        print(invocation.get("StandardOutputContent", ""))
        return
    raise TimeoutError("Inspect the SSM command before retrying domain configuration")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    configure(args.instance, args.sha)
