import os
import shutil

from gateway.compat import run_process


class ClaudeCliRunner(object):
    def __init__(self, settings_path, root_dir, executable="claude"):
        self.settings_path = settings_path
        self.root_dir = root_dir
        self.executable = executable

    def run(self, prompt):
        if not shutil.which(self.executable):
            return "Claude CLI not found in PATH"

        if not os.path.isfile(self.settings_path):
            return "Claude settings file not found: {}".format(self.settings_path)

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
                self.root_dir,
                "--no-session-persistence",
            ]
        )
        output = output.strip()

        if return_code != 0:
            if output:
                return "Claude command failed ({}): {}".format(return_code, output)
            return "Claude command failed with exit code {}".format(return_code)

        if not output:
            return "Claude returned no output"

        return output

