import io
import unittest
from unittest import mock

from gateway import cli


class CliRunTest(unittest.TestCase):
    def test_keyboard_interrupt_exits_cleanly(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        application = mock.Mock()
        application.watch_reply.side_effect = KeyboardInterrupt()

        with mock.patch("gateway.cli.AppConfig.load", return_value=object()):
            with mock.patch("gateway.cli.create_channel", return_value=object()):
                with mock.patch("gateway.cli.create_runner", return_value=object()):
                    with mock.patch(
                        "gateway.cli.GatewayApplication",
                        return_value=application,
                    ):
                        exit_code = cli.run(
                            argv=["app.py", "watch-reply"],
                            stdout=stdout,
                            stderr=stderr,
                            root_dir="/tmp",
                        )

        self.assertEqual(exit_code, 130)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "\n")


if __name__ == "__main__":
    unittest.main()
