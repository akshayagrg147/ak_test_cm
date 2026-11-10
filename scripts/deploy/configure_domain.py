"""Apply an authorized domain to the current ViaCRM release without changing secrets."""

import argparse
import fcntl
import ipaddress
import json
import os
import re
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def hostname(value):
    try:
        address = ipaddress.ip_address(value)
        if address.version != 4:
            raise ValueError("Only the existing IPv4 address is supported")
        return str(address)
    except ValueError:
        if len(value) > 253 or not re.fullmatch(
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
            r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?",
            value,
        ):
            raise ValueError(
                "Expected a lowercase hostname or IPv4, without a scheme or path"
            )
        return value


def replace_values(content, values):
    lines = content.decode().splitlines(keepends=True)
    for key, value in values.items():
        indices = [i for i, line in enumerate(lines) if re.match(rf"\s*{key}=", line)]
        if len(indices) > 1:
            raise ValueError(f"Duplicate managed environment key: {key}")
        replacement = f"{key}={json.dumps(value)}\n"
        if indices:
            lines[indices[0]] = replacement
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(replacement)
    return "".join(lines).encode()


def atomic_write(path, content):
    descriptor, temporary = tempfile.mkstemp(prefix=".domain-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def fetch(url):
    try:
        with urllib.request.build_opener(NoRedirect).open(url, timeout=8) as response:
            return response.status, response.headers, response.read(1024 * 1024)
    except urllib.error.HTTPError as error:
        with error:
            return error.code, error.headers, error.read(1024 * 1024)


def verify(host, aliases, default_sni, sha):
    for address in (host, default_sni):
        status, _, body = fetch(f"https://{address}/api/health")
        health = json.loads(body)
        if status != 200 or not all(
            health.get(k) == "ok" for k in ("status", "database", "worker")
        ):
            raise RuntimeError("Public application, database or worker is not healthy")
    status, _, body = fetch(f"https://{host}/release.json")
    if status != 200 or json.loads(body).get("commit") != sha:
        raise RuntimeError("The public release does not match the expected commit")
    for alias in aliases:
        status, headers, _ = fetch(f"https://{alias}/?domain-check=1")
        if (
            status != 308
            or headers.get("Location") != f"https://{host}/?domain-check=1"
        ):
            raise RuntimeError(
                "An alias does not redirect to the canonical browser origin"
            )


def configure(root, host, aliases, default_sni, expected_release):
    host = hostname(host)
    aliases = list(dict.fromkeys(hostname(alias) for alias in aliases))
    if (
        len(aliases) > 3
        or host in aliases
        or not re.fullmatch(r"[0-9a-f]{40}", expected_release)
    ):
        raise ValueError("Expected a unique primary host and full release SHA")
    default_sni = str(ipaddress.IPv4Address(default_sni))
    if default_sni not in [host, *aliases]:
        raise ValueError("The stable IP must remain a served alias for native clients")
    shared = root / "shared"
    with os.fdopen(
        os.open(shared / "deploy.lock", os.O_CREAT | os.O_RDWR, 0o600), "w"
    ) as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(
                "Another deployment or domain configuration is running"
            ) from None
        release = (root / "current").resolve(strict=True)
        if (
            release != (root / "releases" / expected_release).resolve()
            or release.name != expected_release
        ):
            raise RuntimeError("The expected release is not currently active")
        for filename in ("Caddyfile", "compose.yaml"):
            text = (release / filename).read_text()
            if not all(key in text for key in ("PUBLIC_ALIASES", "TLS_DEFAULT_SNI")):
                raise RuntimeError("The active release does not support domain aliases")
        if (
            f"RELEASE_SHA={expected_release}"
            not in (release / "images.env").read_text().splitlines()
        ):
            raise RuntimeError(
                "The release image manifest does not match the expected commit"
            )
        for address in (host, *aliases):
            resolved = {
                item[4][0]
                for item in socket.getaddrinfo(address, 443, type=socket.SOCK_STREAM)
            }
            if resolved != {default_sni}:
                raise RuntimeError(
                    f"DNS for {address} must point only to the existing server IP"
                )
        paths = [shared / "host.env", shared / "app.env"]
        originals = [path.read_bytes() for path in paths]
        updated = [
            replace_values(
                originals[0],
                {
                    "PUBLIC_HOST": host,
                    "PUBLIC_ALIASES": " ".join(aliases),
                    "TLS_DEFAULT_SNI": default_sni,
                },
            ),
            replace_values(originals[1], {"PUBLIC_ORIGIN": f"https://{host}"}),
        ]
        backups = root / "backups"
        backups.mkdir(mode=0o700, exist_ok=True)
        # Amazon Linux's system Python is 3.9; datetime.UTC requires 3.11.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")  # noqa: UP017
        backup = Path(
            tempfile.mkdtemp(
                prefix="domain-" + stamp + "-",
                dir=backups,
            )
        )
        for path, content in zip(paths, originals):
            atomic_write(backup / path.name, content)
        compose = [
            "docker",
            "compose",
            "--project-name",
            "viacrm",
            "--env-file",
            str(paths[0]),
            "--env-file",
            str(release / "images.env"),
            "-f",
            str(release / "compose.yaml"),
        ]
        overrides = {
            "PUBLIC_HOST",
            "PUBLIC_ALIASES",
            "TLS_DEFAULT_SNI",
            "RELEASE_SHA",
            "API_IMAGE",
            "WEB_IMAGE",
            "CADDY_IMAGE",
            "POSTGRES_IMAGE",
        }
        environment = {
            key: value for key, value in os.environ.items() if key not in overrides
        }
        environment["DEPLOY_ROOT"] = str(root)

        def run(*arguments, timeout=30):
            result = subprocess.run(
                compose + list(arguments),
                env=environment,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
            if result.returncode:
                raise RuntimeError(
                    "Compose operation failed; private environment values were not printed"
                )

        def apply():
            run(
                "up",
                "-d",
                "--wait",
                "--wait-timeout",
                "240",
                "api",
                "worker",
                "https",
                "web",
                timeout=270,
            )

        try:
            for path, content in zip(paths, updated):
                atomic_write(path, content)
            run("config", "--quiet")
            run(
                "run",
                "--rm",
                "--no-deps",
                "https",
                "caddy",
                "validate",
                "--config",
                "/etc/caddy/Caddyfile",
                "--adapter",
                "caddyfile",
                timeout=60,
            )
            apply()
            deadline = time.monotonic() + 240
            while True:
                try:
                    verify(host, aliases, default_sni, expected_release)
                    break
                except (RuntimeError, ValueError, OSError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            "Trusted public HTTPS readiness checks did not pass"
                        ) from None
                    time.sleep(5)
        except Exception as error:
            for path, content in zip(paths, originals):
                atomic_write(path, content)
            try:
                apply()
            except (RuntimeError, OSError, subprocess.SubprocessError):
                raise RuntimeError(
                    f"Domain setup failed; configuration restored but service recovery needs attention. Backup: {backup}"
                ) from error
            raise RuntimeError(
                f"Domain setup failed; prior configuration and services restored. Backup: {backup}"
            ) from error
        print(
            f"Domain https://{host}, legacy API HTTPS and release {expected_release} verified; backup: {backup}"
        )
        return backup


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/opt/viacrm"))
    parser.add_argument("--host", required=True)
    parser.add_argument("--alias", action="append", default=[])
    parser.add_argument("--default-sni", required=True)
    parser.add_argument("--expected-release", required=True)
    arguments = parser.parse_args()
    configure(
        arguments.root,
        arguments.host,
        arguments.alias,
        arguments.default_sni,
        arguments.expected_release,
    )
