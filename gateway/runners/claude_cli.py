import os
import shutil

from gateway.compat import run_process


class ClaudeCliRunner(object):
    def __init__(self, executable, settings_path, workdir, no_session_persistence=False):
        self.executable = executable
        self.settings_path = settings_path
        self.workdir = workdir
        self.no_session_persistence = bool(no_session_persistence)

    def run(self, prompt):
        resolved_executable = shutil.which(self.executable)
        if not resolved_executable:
            return "Claude CLI not found in PATH"

        if not os.path.isfile(self.settings_path):
            return "Claude settings file not found: {}".format(self.settings_path)

        if not os.path.isdir(self.workdir):
            return "Claude workdir not found: {}".format(self.workdir)

        command = [
            resolved_executable,
            "-p",
            prompt,
            "--settings",
            self.settings_path,
            "--permission-mode",
            "bypassPermissions",
            "--dangerously-skip-permissions",
            "--add-dir",
            self.workdir,
        ]
        if self.no_session_persistence:
            command.append("--no-session-persistence")

        return_code, output = run_process(
            command,
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
