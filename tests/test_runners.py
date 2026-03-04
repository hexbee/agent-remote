import unittest
from unittest import mock

from gateway.runners import create_runner
from gateway.runners.claude_cli import ClaudeCliRunner
from gateway.runners.codex_cli import CodexCliRunner


class DummyConfig(object):
    claude_executable = "claude"
    claude_settings_path = "/tmp/settings.json"
    claude_workdir = "/tmp/claude-worktree"
    codex_executable = "codex"
    codex_model = "gpt-5.3-codex"
    codex_reasoning_effort = "high"
    codex_workdir = "/tmp/worktree"
    root_dir = "/tmp/repo"


class RunnerFactoryTest(unittest.TestCase):
    def test_create_runner_returns_claude_runner(self):
        runner = create_runner("claude_cli", DummyConfig())

        self.assertIsInstance(runner, ClaudeCliRunner)
        self.assertEqual(runner.executable, "claude")
        self.assertEqual(runner.settings_path, "/tmp/settings.json")
        self.assertEqual(runner.workdir, "/tmp/claude-worktree")

    def test_create_runner_returns_codex_runner(self):
        runner = create_runner("codex_cli", DummyConfig())

        self.assertIsInstance(runner, CodexCliRunner)
        self.assertEqual(runner.executable, "codex")
        self.assertEqual(runner.model, "gpt-5.3-codex")
        self.assertEqual(runner.reasoning_effort, "high")
        self.assertEqual(runner.workdir, "/tmp/worktree")


class ClaudeCliRunnerTest(unittest.TestCase):
    def test_run_builds_expected_claude_command_and_cwd(self):
        runner = ClaudeCliRunner(
            executable="claude",
            settings_path="/tmp/settings.json",
            workdir="/tmp/claude-worktree",
        )

        with mock.patch("gateway.runners.claude_cli.shutil.which", return_value="/usr/bin/claude"):
            with mock.patch("gateway.runners.claude_cli.os.path.isfile", return_value=True):
                with mock.patch("gateway.runners.claude_cli.os.path.isdir", return_value=True):
                    with mock.patch(
                        "gateway.runners.claude_cli.run_process",
                        return_value=(0, "done\n"),
                    ) as run_process:
                        output = runner.run("your task")

        self.assertEqual(output, "done")
        run_process.assert_called_once_with(
            [
                "claude",
                "-p",
                "your task",
                "--settings",
                "/tmp/settings.json",
                "--permission-mode",
                "bypassPermissions",
                "--dangerously-skip-permissions",
                "--add-dir",
                "/tmp/claude-worktree",
                "--no-session-persistence",
            ],
            cwd="/tmp/claude-worktree",
        )

    def test_run_returns_error_when_workdir_is_missing(self):
        runner = ClaudeCliRunner(
            executable="claude",
            settings_path="/tmp/settings.json",
            workdir="/tmp/missing",
        )

        with mock.patch("gateway.runners.claude_cli.shutil.which", return_value="/usr/bin/claude"):
            with mock.patch("gateway.runners.claude_cli.os.path.isfile", return_value=True):
                with mock.patch("gateway.runners.claude_cli.os.path.isdir", return_value=False):
                    output = runner.run("your task")

        self.assertEqual(output, "Claude workdir not found: /tmp/missing")


class CodexCliRunnerTest(unittest.TestCase):
    def test_run_builds_expected_codex_exec_command(self):
        runner = CodexCliRunner(
            executable="codex",
            model="gpt-5.3-codex",
            reasoning_effort="high",
            workdir="/tmp/worktree",
        )

        with mock.patch("gateway.runners.codex_cli.shutil.which", return_value="/usr/bin/codex"):
            with mock.patch("gateway.runners.codex_cli.os.path.isdir", return_value=True):
                with mock.patch(
                    "gateway.runners.codex_cli.run_process",
                    return_value=(0, "done\n"),
                ) as run_process:
                    output = runner.run("your task")

        self.assertEqual(output, "done")
        run_process.assert_called_once_with(
            [
                "codex",
                "exec",
                "--dangerously-bypass-approvals-and-sandbox",
                "--ephemeral",
                "--skip-git-repo-check",
                "-m",
                "gpt-5.3-codex",
                "-c",
                'model_reasoning_effort="high"',
                "-C",
                "/tmp/worktree",
                "--",
                "your task",
            ]
        )

    def test_run_preserves_prompt_that_starts_with_dash(self):
        runner = CodexCliRunner(
            executable="codex",
            model="gpt-5.3-codex",
            reasoning_effort="high",
            workdir="/tmp/worktree",
        )

        with mock.patch(
            "gateway.runners.codex_cli.shutil.which",
            return_value="/usr/bin/codex",
        ):
            with mock.patch("gateway.runners.codex_cli.os.path.isdir", return_value=True):
                with mock.patch(
                    "gateway.runners.codex_cli.run_process",
                    return_value=(0, "done\n"),
                ) as run_process:
                    output = runner.run("--bogus")

        self.assertEqual(output, "done")
        run_process.assert_called_once_with(
            [
                "codex",
                "exec",
                "--dangerously-bypass-approvals-and-sandbox",
                "--ephemeral",
                "--skip-git-repo-check",
                "-m",
                "gpt-5.3-codex",
                "-c",
                'model_reasoning_effort="high"',
                "-C",
                "/tmp/worktree",
                "--",
                "--bogus",
            ]
        )

    def test_run_returns_error_when_workdir_is_missing(self):
        runner = CodexCliRunner(
            executable="codex",
            model="gpt-5.3-codex",
            reasoning_effort="high",
            workdir="/tmp/missing",
        )

        with mock.patch("gateway.runners.codex_cli.shutil.which", return_value="/usr/bin/codex"):
            with mock.patch("gateway.runners.codex_cli.os.path.isdir", return_value=False):
                output = runner.run("your task")

        self.assertEqual(output, "Codex workdir not found: /tmp/missing")


if __name__ == "__main__":
    unittest.main()
