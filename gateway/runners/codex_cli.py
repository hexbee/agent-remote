import os
import shutil

from gateway.compat import run_process


class CodexCliRunner(object):
    def __init__(
        self,
        executable,
        model,
        reasoning_effort,
        workdir,
    ):
        self.executable = executable
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.workdir = workdir

    def run(self, prompt):
        if not shutil.which(self.executable):
            return "Codex CLI not found in PATH"

        if not os.path.isdir(self.workdir):
            return "Codex workdir not found: {}".format(self.workdir)

        return_code, output = run_process(
            [
                self.executable,
                "exec",
                "--dangerously-bypass-approvals-and-sandbox",
                "--ephemeral",
                "--skip-git-repo-check",
                "-m",
                self.model,
                "-c",
                'model_reasoning_effort="{}"'.format(
                    _escape_config_string(self.reasoning_effort)
                ),
                "-C",
                self.workdir,
                "--",
                prompt,
            ]
        )
        output = output.strip()

        if return_code != 0:
            if output:
                return "Codex command failed ({}): {}".format(return_code, output)
            return "Codex command failed with exit code {}".format(return_code)

        if not output:
            return "Codex returned no output"

        return output


def _escape_config_string(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')
