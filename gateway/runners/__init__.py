from gateway.runners.claude_cli import ClaudeCliRunner


def create_runner(name, config):
    if name != "claude_cli":
        raise ValueError("Unsupported runner: {}".format(name))

    return ClaudeCliRunner(
        settings_path=config.claude_settings_path,
        root_dir=config.root_dir,
    )

