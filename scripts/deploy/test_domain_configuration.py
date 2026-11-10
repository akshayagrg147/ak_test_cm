import contextlib
import fcntl
import importlib.util
import io
import json
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "configure_domain", Path(__file__).with_name("configure_domain.py")
)
DOMAIN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOMAIN)
SHA = "a" * 40
HOST = "viacrm.in"
IP = "13.234.72.21"
ALIASES = ["www.viacrm.in", IP]


class DomainConfiguration(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.shared = self.root / "shared"
        self.shared.mkdir(mode=0o700)
        self.release = self.root / "releases" / SHA
        self.release.mkdir(parents=True)
        (self.root / "current").symlink_to(self.release)
        for name in ("Caddyfile", "compose.yaml"):
            (self.release / name).write_text("PUBLIC_ALIASES TLS_DEFAULT_SNI")
        (self.release / "images.env").write_text(f"RELEASE_SHA={SHA}\n")
        self.before = {
            "host.env": b"AWS_REGION=ap-south-1\nPUBLIC_HOST=13.234.72.21\nRELEASE_BUCKET=private-bucket\n",
            "app.env": b'# preserve this comment\nSECRET_KEY="never-print-this"\nENCRYPTION_KEY="same-encryption-key"\nPUBLIC_ORIGIN="https://13.234.72.21"\nDATABASE_URL="postgresql://crm:secret@db/crm"\n',
        }
        for name, content in self.before.items():
            (self.shared / name).write_bytes(content)
        self.dns = patch.object(
            DOMAIN.socket,
            "getaddrinfo",
            return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (IP, 443))],
        ).start()
        self.runner = patch.object(
            DOMAIN.subprocess, "run", return_value=SimpleNamespace(returncode=0)
        ).start()
        self.verify = patch.object(DOMAIN, "verify").start()
        self.addCleanup(patch.stopall)

    def configure(self, **changes):
        values = {
            "root": self.root,
            "host": HOST,
            "aliases": ALIASES,
            "default_sni": IP,
            "expected_release": SHA,
        }
        values.update(changes)
        return DOMAIN.configure(**values)

    def test_success_preserves_secrets_and_private_backups_and_recreates_services(self):
        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            patch.dict(
                DOMAIN.os.environ,
                {"PUBLIC_HOST": "wrong.example", "API_IMAGE": "untrusted:latest"},
            ),
        ):
            backup = self.configure()
        app = (self.shared / "app.env").read_bytes()
        for line in self.before["app.env"].splitlines(keepends=True):
            if not line.startswith(b"PUBLIC_ORIGIN="):
                self.assertIn(line, app)
        self.assertIn(b'PUBLIC_ORIGIN="https://viacrm.in"\n', app)
        host = (self.shared / "host.env").read_bytes()
        self.assertIn(b'PUBLIC_HOST="viacrm.in"\n', host)
        self.assertIn(b'PUBLIC_ALIASES="www.viacrm.in 13.234.72.21"\n', host)
        self.assertIn(b'TLS_DEFAULT_SNI="13.234.72.21"\n', host)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        for name, content in self.before.items():
            self.assertEqual((backup / name).read_bytes(), content)
            self.assertEqual((backup / name).stat().st_mode & 0o777, 0o600)
            self.assertEqual((self.shared / name).stat().st_mode & 0o777, 0o600)
        commands = [call.args[0] for call in self.runner.call_args_list]
        self.assertEqual(
            commands[-1][-10:],
            [
                "up",
                "-d",
                "--force-recreate",
                "--wait",
                "--wait-timeout",
                "240",
                "api",
                "worker",
                "https",
                "web",
            ],
        )
        self.assertTrue(any("validate" in command for command in commands))
        self.assertFalse(
            any(
                "restart" in command or "down" in command or "alembic" in command
                for command in commands
            )
        )
        for call in self.runner.call_args_list:
            self.assertNotIn("API_IMAGE", call.kwargs["env"])
            self.assertNotIn("PUBLIC_HOST", call.kwargs["env"])
            self.assertEqual(call.kwargs["env"]["DEPLOY_ROOT"], str(self.root))
        self.verify.assert_called_once_with(HOST, ALIASES, IP, SHA)
        self.assertNotIn("never-print-this", output.getvalue())
        self.assertIn(SHA, output.getvalue())

    def test_invalid_input_is_rejected_before_any_operation(self):
        invalid = [
            "https://viacrm.in",
            "viacrm.in/path",
            "bad..example",
            "x.example\nSECRET_KEY=bad",
            "$(touch bad)",
            "Upper.example",
            "*.viacrm.in",
        ]
        for host in invalid:
            with self.subTest(host=host), self.assertRaises(ValueError):
                self.configure(host=host)
        for changes in (
            {"expected_release": "main"},
            {"aliases": [HOST, IP]},
            {"aliases": ["www.viacrm.in"]},
            {"default_sni": "::1"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.configure(**changes)
        self.runner.assert_not_called()

    def test_wrong_dns_or_extra_ipv6_does_not_change_environment(self):
        for addresses in (["203.0.113.5"], [IP, "2001:db8::1"]):
            self.dns.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
                for address in addresses
            ]
            with (
                self.subTest(addresses=addresses),
                self.assertRaisesRegex(RuntimeError, "DNS"),
            ):
                self.configure()
            self.assert_originals()
        self.runner.assert_not_called()
        self.assertFalse((self.root / "backups").exists())

    def test_inactive_release_missing_support_or_wrong_manifest_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "not currently active"):
            self.configure(expected_release="b" * 40)
        (self.release / "Caddyfile").write_text("old config")
        with self.assertRaisesRegex(RuntimeError, "does not support"):
            self.configure()
        (self.release / "Caddyfile").write_text("PUBLIC_ALIASES TLS_DEFAULT_SNI")
        (self.release / "images.env").write_text("RELEASE_SHA=" + "b" * 40)
        with self.assertRaisesRegex(RuntimeError, "manifest"):
            self.configure()
        self.assert_originals()
        self.runner.assert_not_called()

    def test_lock_prevents_concurrent_deployment(self):
        with (self.shared / "deploy.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError, "Another deployment"):
                self.configure()
        self.assert_originals()
        self.runner.assert_not_called()

    def test_validation_failure_restores_both_environments_and_services(self):
        self.runner.side_effect = [
            SimpleNamespace(returncode=0),
            SimpleNamespace(returncode=1),
            SimpleNamespace(returncode=0),
        ]
        with self.assertRaisesRegex(
            RuntimeError, "prior configuration and services restored"
        ):
            self.configure()
        self.assert_originals()
        self.assertIn("up", self.runner.call_args.args[0])
        self.assertEqual(len(list((self.root / "backups").glob("domain-*"))), 1)

    def test_readiness_failure_restores_previous_configuration_without_secret_output(
        self,
    ):
        self.verify.side_effect = [RuntimeError("not ready"), None]
        with (
            patch.object(DOMAIN.time, "monotonic", side_effect=[100, 341]),
            self.assertRaisesRegex(
                RuntimeError, "prior configuration and services restored"
            ),
        ):
            self.configure()
        self.assert_originals()
        self.assertEqual(self.verify.call_args.args, (IP, [], IP, SHA))
        self.assertEqual(
            sum("up" in call.args[0] for call in self.runner.call_args_list), 2
        )
        for call in self.runner.call_args_list:
            if "up" in call.args[0]:
                # Both activation and rollback replace API containers; an
                # unchanged web container would retain their old IP in Nginx.
                self.assertIn("--force-recreate", call.args[0])
                self.assertIn("web", call.args[0])

    def test_failed_rollback_reports_operator_attention(self):
        self.runner.return_value = SimpleNamespace(returncode=1)
        with self.assertRaisesRegex(RuntimeError, "service recovery needs attention"):
            self.configure()
        self.assert_originals()

    def test_rollback_public_api_failure_does_not_claim_restoration(self):
        self.runner.side_effect = [
            SimpleNamespace(returncode=1),
            SimpleNamespace(returncode=0),
        ]
        self.verify.side_effect = RuntimeError("Public API still returns 502")
        with self.assertRaisesRegex(RuntimeError, "service recovery needs attention"):
            self.configure()
        self.assert_originals()
        self.verify.assert_called_once_with(IP, [], IP, SHA)

    def assert_originals(self):
        for name, content in self.before.items():
            self.assertEqual((self.shared / name).read_bytes(), content)


class PublicReadiness(unittest.TestCase):
    def responses(self, url):
        if url.endswith("/api/health"):
            return (
                200,
                {},
                json.dumps({"status": "ok", "database": "ok", "worker": "ok"}).encode(),
            )
        if url.endswith("/release.json"):
            return 200, {}, json.dumps({"commit": SHA}).encode()
        return 308, {"Location": "https://viacrm.in/?domain-check=1"}, b""

    def test_canonical_release_legacy_api_and_alias_redirects(self):
        with patch.object(DOMAIN, "fetch", side_effect=self.responses) as fetch:
            DOMAIN.verify(HOST, ALIASES, IP, SHA)
        self.assertIn(
            "https://13.234.72.21/api/health",
            [call.args[0] for call in fetch.call_args_list],
        )

    def test_legacy_api_redirect_and_wrong_release_are_rejected(self):
        def legacy_redirect(url):
            if url == "https://13.234.72.21/api/health":
                return 308, {"Location": "https://viacrm.in/api/health"}, b"{}"
            return self.responses(url)

        with (
            patch.object(DOMAIN, "fetch", side_effect=legacy_redirect),
            self.assertRaises(RuntimeError),
        ):
            DOMAIN.verify(HOST, ALIASES, IP, SHA)
        with (
            patch.object(DOMAIN, "fetch", side_effect=self.responses),
            self.assertRaisesRegex(RuntimeError, "expected commit"),
        ):
            DOMAIN.verify(HOST, ALIASES, IP, "b" * 40)

    def test_wrong_alias_destination_is_rejected(self):
        def wrong_alias(url):
            if url.startswith("https://www.viacrm.in/"):
                return 308, {"Location": "https://unrelated.example/"}, b""
            return self.responses(url)

        with (
            patch.object(DOMAIN, "fetch", side_effect=wrong_alias),
            self.assertRaisesRegex(RuntimeError, "canonical browser origin"),
        ):
            DOMAIN.verify(HOST, ALIASES, IP, SHA)


if __name__ == "__main__":
    unittest.main()
