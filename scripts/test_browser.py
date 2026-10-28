"""Run browser journeys on disposable PostgreSQL/API/worker/web services, never the working CRM."""

import argparse
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def free_port(port):
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", port))
        return probe.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", choices=["chromium", "firefox", "webkit"], default="chromium")
    parser.add_argument("--api-port", type=int, default=0, help="API port; default chooses an unused port")
    parser.add_argument("--web-port", type=int, default=0, help="Web port; default chooses an unused port")
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--production", action="store_true", help="Serve the built dist bundle through Vite preview")
    parser.add_argument("tests", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.api_port and args.api_port == args.web_port:
        parser.error("API and website need different ports")
    try:
        args.api_port = free_port(args.api_port)
        args.web_port = free_port(args.web_port)
        while args.api_port == args.web_port:
            args.web_port = free_port(0)
    except OSError as exc:
        parser.error(f"Cannot use the requested local port: {exc}")
    node = shutil.which("node")
    if not node:
        parser.error("Node.js is required; use the project .nvmrc runtime")
    version = subprocess.check_output([node, "-p", "process.versions.node"], text=True).strip()
    major, minor, *_ = map(int, version.split("."))
    if not ((major == 20 and minor >= 19) or (major == 22 and minor >= 12) or major >= 23):
        parser.error(f"Node {version} does not satisfy the installed Vite runtime; use .nvmrc")
    if args.production and not (ROOT / "web/dist/index.html").is_file():
        parser.error("Run npm run build in web/ before --production")
    configured = {key: value for key, value in dotenv_values(ROOT / ".env").items() if value is not None}
    configured.update(os.environ)
    database_url = make_url(configured.get("DATABASE_URL", "postgresql+psycopg://127.0.0.1:55432/talkocrm"))
    database = "aven_browser_" + secrets.token_hex(6) + "_test"
    assert re.fullmatch(r"aven_browser_[a-f0-9]{12}_test", database)
    report = (args.artifacts or ROOT / "artifacts" / ("browser-" + database)).resolve()
    report.mkdir(parents=True, exist_ok=True)
    (ROOT / ".local").mkdir(exist_ok=True)
    admin = create_engine(database_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    processes = []
    created = False
    result = 1
    with tempfile.TemporaryDirectory(prefix="browser-test-", dir=ROOT / ".local") as temporary:
        local = Path(temporary)
        env = configured.copy()
        env.update(
            DATABASE_URL=database_url.set(database=database).render_as_string(hide_password=False),
            ENVIRONMENT="test",
            SECRET_KEY=secrets.token_urlsafe(48),
            ENCRYPTION_KEY=Fernet.generate_key().decode(),
            STORAGE_PATH=str(local / "storage"),
            PUBLIC_ORIGIN=f"http://localhost:{args.web_port}",
            API_PROXY_TARGET=f"http://127.0.0.1:{args.api_port}",
            E2E_BASE_URL=f"http://localhost:{args.web_port}",
            E2E_BROWSER=args.browser,
            E2E_ARTIFACT_DIR=str(report),
            E2E_PYTHON_BINARY=sys.executable,
        )
        env["E2E_TEST_DATABASE_URL"] = env["DATABASE_URL"]
        try:
            with admin.connect() as connection:
                connection.execute(text(f'CREATE DATABASE "{database}"'))
            created = True
            with (local / "bootstrap.log").open("w") as log:
                subprocess.run(
                    [sys.executable, "-m", "alembic", "upgrade", "head"],
                    cwd=ROOT / "backend",
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
                seed_env = {**env, "ENVIRONMENT": "development"}
                subprocess.run(
                    [sys.executable, "-m", "app.seed"],
                    cwd=ROOT / "backend",
                    env=seed_env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
            web_args = [node, str(ROOT / "web/node_modules/vite/bin/vite.js")]
            if args.production:
                # Keep an in-progress local rebuild from replacing assets during a journey.
                shutil.copytree(ROOT / "web/dist", local / "dist")
                web_args += ["preview", "--outDir", str(local / "dist")]
            web_args += ["--host", "127.0.0.1", "--port", str(args.web_port), "--strictPort"]
            for label, command, cwd in [
                (
                    "api",
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(args.api_port),
                    ],
                    ROOT / "backend",
                ),
                ("worker", [sys.executable, "-m", "app.worker"], ROOT / "backend"),
                ("web", web_args, ROOT / "web"),
            ]:
                with (local / f"{label}.log").open("w") as log:
                    processes.append(
                        subprocess.Popen(
                            command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
                        )
                    )
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen(env["E2E_BASE_URL"] + "/api/health", timeout=2) as response:
                        if response.status == 200:
                            break
                except (OSError, ValueError):
                    pass
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError("An isolated service stopped during startup")
                time.sleep(0.25)
            else:
                raise RuntimeError("The isolated website did not become healthy")
            arguments = args.tests[1:] if args.tests[:1] == ["--"] else args.tests
            print(f"Testing {args.browser} on isolated services; report: {report}", flush=True)
            result = subprocess.run(
                [node, str(ROOT / "web/node_modules/playwright/cli.js"), "test", *arguments],
                cwd=ROOT / "web",
                env=env,
                check=False,
            ).returncode
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=5)
                    except ProcessLookupError:
                        pass
            # This generated name cannot select or truncate the development database.
            if created:
                with admin.connect() as connection:
                    connection.execute(
                        text(
                            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name AND pid<>pg_backend_pid()"
                        ),
                        {"name": database},
                    )
                    connection.execute(text(f'DROP DATABASE "{database}"'))
            admin.dispose()
            sensitive = [env[key] for key in ["SECRET_KEY", "ENCRYPTION_KEY"]]
            if database_url.password:
                sensitive.append(database_url.password)
            for log in local.glob("*.log"):
                contents = log.read_text(errors="replace")
                for value in sensitive:
                    contents = contents.replace(value, "[redacted]")
                (report / log.name).write_text(contents)
    print("Isolated services stopped and temporary test database removed.", flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
