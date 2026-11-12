"""Verify production Caddy adaptation and routing without public TLS or CRM writes."""

import argparse
import copy
import http.client
import json
import os
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY_IP = "13.234.72.21"


class Upstream(BaseHTTPRequestHandler):
    name = "web"

    def reply(self):
        size = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(size)
        payload = {"method": self.command, "path": self.path}
        if self.name != "web":
            payload["upstream"] = self.name
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = do_PATCH = reply

    def log_message(self, *_):
        pass


class BotUpstream(Upstream):
    name = "igbot"


def nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def request(port, host, path, method="GET", body=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(
            method,
            path,
            body=body if body is not None else (b"{}" if method != "GET" else None),
            headers={"Host": host},
        )
        response = connection.getresponse()
        return response.status, response.getheader("Location"), response.read()
    finally:
        connection.close()


def verify(caddy, primary, aliases):
    with tempfile.TemporaryDirectory(prefix="viacrm-caddy-check-") as directory:
        temporary = Path(directory)
        env = {
            **os.environ,
            **{
                f"{name}_IMAGE": f"verification/{name.lower()}@sha256:" + "a" * 64
                for name in ["API", "WEB", "POSTGRES", "CADDY", "IGBOT"]
            },
            "RELEASE_SHA": "a" * 40,
            "PUBLIC_HOST": primary,
            "XDG_DATA_HOME": str(temporary / "data"),
            "XDG_CONFIG_HOME": str(temporary / "config"),
        }
        for optional in ["PUBLIC_ALIASES", "TLS_DEFAULT_SNI"]:
            env.pop(optional, None)
        if aliases:
            env.update(PUBLIC_ALIASES=" ".join(aliases), TLS_DEFAULT_SNI=LEGACY_IP)
        rendered = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(ROOT / "infra/compose.production.yaml"),
                "config",
                "--no-env-resolution",
                "--format",
                "json",
            ],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=20,
        )
        https_env = json.loads(rendered.stdout)["services"]["https"]["environment"]
        assert https_env == {
            "PUBLIC_HOST": primary,
            "PUBLIC_ALIASES": " ".join(aliases),
            "TLS_DEFAULT_SNI": LEGACY_IP,
        }, https_env
        env.update(https_env)
        command = [
            str(caddy),
            "adapt",
            "--config",
            str(ROOT / "infra/Caddyfile.production"),
            "--adapter",
            "caddyfile",
        ]
        adapted = subprocess.run(
            command, env=env, capture_output=True, text=True, check=True, timeout=20
        )
        config = json.loads(adapted.stdout)
        subprocess.run(
            [
                str(caddy),
                "validate",
                "--config",
                str(ROOT / "infra/Caddyfile.production"),
                "--adapter",
                "caddyfile",
            ],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=20,
        )
        expected_hosts = {primary, *aliases}
        policies = config["apps"]["tls"]["automation"]["policies"]
        assert {
            host for policy in policies for host in policy["subjects"]
        } == expected_hosts
        for policy in policies:
            assert policy["issuers"] == [
                {
                    "module": "acme",
                    "ca": "https://acme-v02.api.letsencrypt.org/directory",
                    "profile": "shortlived",
                }
            ]
        servers = config["apps"]["http"]["servers"]
        assert len(servers) == 1
        server = next(iter(servers.values()))
        assert {
            policy["default_sni"] for policy in server["tls_connection_policies"]
        } == {LEGACY_IP}

        # Exercise the adapted handlers on loopback, replacing only transport
        # and upstream addresses. Certificate issuance and public ports stay off.
        loopback = copy.deepcopy(config)
        loopback["apps"].pop("tls")
        local = next(iter(loopback["apps"]["http"]["servers"].values()))
        local.pop("tls_connection_policies")
        local["automatic_https"] = {"disable": True}
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        local["listen"] = [f"127.0.0.1:{port}"]
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        bot = ThreadingHTTPServer(("127.0.0.1", 0), BotUpstream)
        thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        bot_thread = threading.Thread(target=bot.serve_forever, daemon=True)
        thread.start()
        bot_thread.start()
        process = None
        dials = {"web:80": upstream.server_port, "igbot:8080": bot.server_port}
        try:
            seen = set()
            for node in nodes(loopback):
                if node.get("handler") == "reverse_proxy":
                    [original] = [u["dial"] for u in node["upstreams"]]
                    seen.add(original)
                    node["upstreams"] = [{"dial": f"127.0.0.1:{dials[original]}"}]
            assert seen == set(dials), seen
            local_config = temporary / "loopback.json"
            local_config.write_text(json.dumps(loopback))
            with (temporary / "caddy.log").open("w+") as log:
                process = subprocess.Popen(
                    [str(caddy), "run", "--config", str(local_config)],
                    env=env,
                    stdout=log,
                    stderr=log,
                )
                deadline = time.monotonic() + 10
                while True:
                    if process.poll() is not None:
                        log.seek(0)
                        raise RuntimeError(
                            "Loopback Caddy exited: " + log.read()[-3000:]
                        )
                    try:
                        assert request(port, primary, "/api/health")[0] == 200
                        break
                    except (OSError, http.client.HTTPException):
                        if time.monotonic() >= deadline:
                            raise RuntimeError(
                                "Loopback Caddy did not become ready"
                            ) from None
                        time.sleep(0.05)
                for host in expected_hosts:
                    for path in ["/", "/app/leads?search=a%20b&next=%2Fapp", "/apiary"]:
                        status, location, body = request(port, host, path)
                        if host == primary:
                            assert status == 200 and location is None, (
                                host,
                                path,
                                status,
                                location,
                            )
                            assert json.loads(body) == {"method": "GET", "path": path}
                        else:
                            assert (status, location) == (
                                308,
                                f"https://{primary}{path}",
                            ), (host, path, status, location)
                    for method, path in [
                        ("GET", "/api"),
                        ("GET", "/api/"),
                        ("GET", "/api/health?probe=1"),
                        ("POST", "/api/auth/refresh"),
                        ("PATCH", "/api/field-work/example"),
                    ]:
                        status, location, body = request(port, host, path, method)
                        assert status == 200 and location is None, (
                            host,
                            method,
                            path,
                            status,
                            location,
                        )
                        assert json.loads(body) == {"method": method, "path": path}
                    # The Instagram webhook reaches only the bot, on the canonical host.
                    for method, path in [
                        ("GET", "/ig-webhook?hub.mode=subscribe&hub.challenge=1"),
                        ("POST", "/ig-webhook"),
                        ("GET", "/ig-webhook/health"),
                    ]:
                        status, location, body = request(port, host, path, method)
                        if host == primary:
                            assert status == 200 and json.loads(body) == {
                                "method": method,
                                "path": path,
                                "upstream": "igbot",
                            }, (host, method, path, status, body)
                        else:
                            assert (status, location) == (
                                308,
                                f"https://{primary}{path}",
                            ), (host, method, path, status, location)
                status, _, _ = request(
                    port, primary, "/ig-webhook", "POST", b"x" * (1024 * 1024 + 1)
                )
                assert status == 413, f"oversized webhook body returned {status}"
        finally:
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            for server, worker in [(upstream, thread), (bot, bot_thread)]:
                server.shutdown()
                server.server_close()
                worker.join(timeout=2)
        print(
            f"Verified {primary}: TLS policy and {len(expected_hosts)} host(s), aliases redirect pages only, /ig-webhook to the bot with a 1 MB limit"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caddy", type=Path, required=True)
    args = parser.parse_args()
    binary = args.caddy.resolve()
    version = subprocess.run(
        [str(binary), "version"], capture_output=True, text=True, check=True, timeout=10
    ).stdout.strip()
    print(version)
    verify(binary, LEGACY_IP, [])
    verify(binary, "viacrm.in", ["www.viacrm.in", LEGACY_IP])
