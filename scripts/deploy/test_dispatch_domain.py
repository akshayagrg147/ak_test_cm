import contextlib
import io
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import dispatch_domain

SHA = "a" * 40
INSTANCE = "i-0123456789abcdef0"
COMMAND_ID = "12345678-1234-1234-1234-123456789012"


def invocation(status, **extra):
    return subprocess.CompletedProcess(
        [], 0, json.dumps({"Status": status, **extra}), ""
    )


class Clock:
    value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class DispatchDomain(unittest.TestCase):
    @contextlib.contextmanager
    def polling(self, replies):
        clock = Clock()
        output = io.StringIO()
        with (
            patch.object(
                dispatch_domain,
                "aws",
                return_value={"Command": {"CommandId": COMMAND_ID}},
            ) as send,
            patch.object(dispatch_domain.subprocess, "run", side_effect=replies) as run,
            patch.object(
                dispatch_domain.time, "monotonic", side_effect=clock.monotonic
            ),
            patch.object(dispatch_domain.time, "sleep", side_effect=clock.sleep),
            contextlib.redirect_stdout(output),
        ):
            yield send, run, clock, output

    def test_invalid_instance_or_commit_cannot_submit_or_poll(self):
        invalid = [
            ("i-1234; echo unsafe", SHA),
            ("i-1234\n", SHA),
            ("", SHA),
            (INSTANCE, "main"),
            (INSTANCE, "a" * 39),
            (INSTANCE, "A" * 40),
            (INSTANCE, SHA + "'; echo unsafe"),
        ]
        for instance, sha in invalid:
            with (
                self.subTest(instance=instance, sha=sha),
                self.polling([]) as (send, run, _, _),
            ):
                with self.assertRaises(ValueError):
                    dispatch_domain.configure(instance, sha)
                send.assert_not_called()
                run.assert_not_called()

    def test_remote_command_requires_exact_current_release_and_fixed_domain(self):
        script = (
            dispatch_domain.command(SHA).split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            release = root / "releases" / SHA
            release.mkdir(parents=True)
            current = root / "current"
            current.symlink_to(release, target_is_directory=True)
            run = Mock()
            modules = {
                "pathlib": types.SimpleNamespace(
                    Path=lambda value: root if value == "/opt/viacrm" else Path(value)
                ),
                "subprocess": types.SimpleNamespace(run=run),
            }
            with (
                patch.dict(sys.modules, modules),
                patch.object(sys, "argv", ["-", SHA]),
            ):
                # Execute only the committed fixed heredoc with filesystem/process
                # modules replaced, proving its guards before any real command.
                exec(compile(script, "<domain-ssm-command>", "exec"), {})  # noqa: S102
            run.assert_called_once_with(
                [
                    sys.executable,
                    str(release / "configure_domain.py"),
                    "--host",
                    "viacrm.in",
                    "--alias",
                    "www.viacrm.in",
                    "--alias",
                    "13.234.72.21",
                    "--default-sni",
                    "13.234.72.21",
                    "--expected-release",
                    SHA,
                ],
                check=True,
            )
            for target in [
                root / "releases" / ("b" * 40),
                root / "outside" / SHA,
                None,
            ]:
                with self.subTest(target=target):
                    current.unlink()
                    if target is not None:
                        target.mkdir(parents=True)
                        current.symlink_to(target, target_is_directory=True)
                    run.reset_mock()
                    with (
                        patch.dict(sys.modules, modules),
                        patch.object(sys, "argv", ["-", SHA]),
                        self.assertRaises((RuntimeError, FileNotFoundError)),
                    ):
                        exec(compile(script, "<domain-ssm-command>", "exec"), {})  # noqa: S102
                    run.assert_not_called()
                    if target is None:
                        break

    def test_submission_has_cli_and_process_limits_with_automatic_retries_disabled(
        self,
    ):
        result = subprocess.CompletedProcess(
            [], 0, '{"Command":{"CommandId":"example"}}', ""
        )
        with patch.object(
            dispatch_domain.subprocess, "run", return_value=result
        ) as run:
            self.assertEqual(
                dispatch_domain.aws("ssm", "send-command"), json.loads(result.stdout)
            )
        arguments, kwargs = run.call_args
        command = arguments[0]
        self.assertEqual(command[:3], ["aws", "ssm", "send-command"])
        self.assertEqual(command[command.index("--cli-connect-timeout") + 1], "10")
        self.assertEqual(command[command.index("--cli-read-timeout") + 1], "20")
        self.assertEqual(kwargs["timeout"], 30)
        self.assertEqual(kwargs["env"]["AWS_MAX_ATTEMPTS"], "1")
        self.assertNotIn("shell", kwargs)

    def test_ambiguous_submission_timeout_is_not_retried_or_logged(self):
        output = io.StringIO()
        failure = subprocess.TimeoutExpired(
            "aws", 30, output="private-output", stderr="private-error"
        )
        with (
            patch.object(dispatch_domain.subprocess, "run", side_effect=failure) as run,
            contextlib.redirect_stdout(output),
            self.assertRaisesRegex(TimeoutError, "inspect recent commands") as error,
        ):
            dispatch_domain.aws("ssm", "send-command")
        self.assertEqual(run.call_count, 1)
        self.assertNotIn("private", output.getvalue() + str(error.exception))

    def test_submission_error_does_not_expose_aws_output(self):
        result = subprocess.CompletedProcess([], 1, "private-output", "private-error")
        with (
            patch.object(dispatch_domain.subprocess, "run", return_value=result) as run,
            self.assertRaisesRegex(RuntimeError, "inspect recent commands") as error,
        ):
            dispatch_domain.aws("ssm", "send-command")
        self.assertEqual(run.call_count, 1)
        self.assertNotIn("private", str(error.exception))

    def test_eventual_invocation_and_progress_complete_without_resubmission(self):
        replies = [
            subprocess.CompletedProcess([], 1, "", "InvocationDoesNotExist"),
            invocation("Pending"),
            invocation("Delayed"),
            invocation("InProgress"),
            invocation("Success", StandardOutputContent="Public HTTPS verified"),
        ]
        with self.polling(replies) as (send, run, _, output):
            dispatch_domain.configure(INSTANCE, SHA)
        send.assert_called_once()
        arguments = send.call_args.args
        self.assertEqual(arguments[arguments.index("--instance-ids") + 1], INSTANCE)
        self.assertEqual(
            arguments[arguments.index("--document-name") + 1], "AWS-RunShellScript"
        )
        self.assertEqual(arguments[arguments.index("--timeout-seconds") + 1], "600")
        parameters = json.loads(arguments[arguments.index("--parameters") + 1])
        self.assertEqual(
            parameters,
            {"commands": [dispatch_domain.command(SHA)], "executionTimeout": ["1200"]},
        )
        self.assertEqual(run.call_count, len(replies))
        for call in run.call_args_list:
            command = call.args[0]
            self.assertEqual(command[command.index("--instance-id") + 1], INSTANCE)
            self.assertEqual(command[command.index("--command-id") + 1], COMMAND_ID)
            self.assertLessEqual(call.kwargs["timeout"], 30)
            self.assertEqual(call.kwargs["env"]["AWS_MAX_ATTEMPTS"], "1")
        self.assertIn(COMMAND_ID, output.getvalue())
        self.assertIn("Public HTTPS verified", output.getvalue())

    def test_terminal_failure_is_reported_once_without_remote_error_contents(self):
        for status in ["Failed", "Cancelled", "TimedOut", "Cancelling"]:
            with (
                self.subTest(status=status),
                self.polling(
                    [
                        invocation(
                            status,
                            StandardOutputContent="private-output",
                            StandardErrorContent="private-error",
                        )
                    ]
                ) as (send, run, _, output),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, f"Domain configuration failed: {status}"
                ):
                    dispatch_domain.configure(INSTANCE, SHA)
                self.assertEqual(send.call_count, 1)
                self.assertEqual(run.call_count, 1)
                self.assertNotIn("private", output.getvalue())

    def test_unexpected_aws_error_is_not_hidden_or_retried(self):
        with self.polling(
            [subprocess.CompletedProcess([], 1, "private-output", "private-error")]
        ) as (send, run, _, output):
            with self.assertRaisesRegex(
                RuntimeError, "Unable to read the SSM result"
            ) as error:
                dispatch_domain.configure(INSTANCE, SHA)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(run.call_count, 1)
            self.assertNotIn("private", output.getvalue() + str(error.exception))

    def test_poll_timeout_never_resubmits_an_accepted_command(self):
        with self.polling([subprocess.TimeoutExpired("aws", 30)]) as (send, run, _, _):
            with self.assertRaisesRegex(
                TimeoutError, "inspect the command before retrying"
            ):
                dispatch_domain.configure(INSTANCE, SHA)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(run.call_count, 1)

    def test_wall_clock_deadline_includes_slow_aws_calls_and_caps_last_call(self):
        with self.polling([]) as (send, run, clock, _):

            def slow_poll(*_, **kwargs):
                clock.value += min(29, kwargs["timeout"])
                return invocation("InProgress")

            run.side_effect = slow_poll
            with self.assertRaisesRegex(TimeoutError, "Inspect the SSM command"):
                dispatch_domain.configure(INSTANCE, SHA)
            self.assertEqual(send.call_count, 1)
            self.assertLessEqual(clock.value, dispatch_domain.POLL_SECONDS)
            self.assertLess(run.call_args.kwargs["timeout"], 30)


if __name__ == "__main__":
    unittest.main()
