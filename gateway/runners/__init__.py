from gateway.runners.claude_cli import ClaudeCliRunner
from gateway.runners.codex_cli import CodexCliRunner


def create_runner(name, config):
    if name == "claude_cli":
        return ClaudeCliRunner(
            executable=config.claude_executable,
            settings_path=config.claude_settings_path,
            workdir=config.claude_workdir,
        )

    if name == "codex_cli":
        return CodexCliRunner(
            executable=config.codex_executable,
            model=config.codex_model,
            reasoning_effort=config.codex_reasoning_effort,
            workdir=config.codex_workdir,
        )

    raise ValueError("Unsupported runner: {}".format(name))
