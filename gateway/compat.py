import subprocess


class GatewayError(Exception):
    """Base gateway error."""


class ConfigError(GatewayError):
    """Raised when configuration is invalid."""


class CommandError(GatewayError):
    """Raised when CLI usage is invalid."""


class ApiError(GatewayError):
    """Raised when an upstream API call fails."""


def run_process(args, cwd=None):
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
    )
    output = process.communicate()[0] or b""
    return process.returncode, output.decode("utf-8", "replace")

