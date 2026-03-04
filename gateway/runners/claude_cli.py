import os
import shutil

from gateway.compat import run_process


class ClaudeCliRunner(object):
    def __init__(self, executable, settings_path, workdir):
        self.executable = executable
        self.settings_path = settings_path
        self.workdir = workdir

    def run(self, prompt):
        if not shutil.which(self.executable):
            return "Claude CLI not found in PATH"

        if not os.path.isfile(self.settings_path):
            return "Claude settings file not found: {}".format(self.settings_path)

        if not os.path.isdir(self.workdir):
            return "Claude workdir not found: {}".format(self.workdir)

        return_code, output = run_process(
            [
                self.executable,
                "-p",
                prompt,
                "--settings",
                self.settings_path,
                "--permission-mode",
                "bypassPermissions",
                "--dangerously-skip-permissions",
                "--add-dir",
                self.workdir,
                "--no-session-persistence",
            ],
            cwd=self.workdir,
        )
        output = output.strip()

        if return_code != 0:
            if output:
                return "Claude command failed ({}): {}".format(return_code, output)
            return "Claude command failed with exit code {}".format(return_code)

        if not output:
            return "Claude returned no output"

        return output
