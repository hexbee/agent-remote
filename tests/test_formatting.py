import unittest

from gateway.formatting import (
    TRUNCATION_SUFFIX,
    extract_next_offset,
    format_updates,
    limit_message_length,
    normalize_heartbeat_text,
    preview_text,
)


class FormattingTest(unittest.TestCase):
    def test_limit_message_length_truncates_with_suffix(self):
        text = "x" * 30
        limited = limit_message_length(text, 20)

        self.assertEqual(len(limited), 20)
        self.assertTrue(limited.endswith(TRUNCATION_SUFFIX))

    def test_limit_message_length_hard_cuts_when_limit_is_tiny(self):
        self.assertEqual(limit_message_length("abcdef", 5), "abcde")

    def test_preview_text_normalizes_newlines(self):
        self.assertEqual(preview_text("a\nb\rc", 20), "a b c")

    def test_normalize_heartbeat_text(self):
        self.assertEqual(normalize_heartbeat_text("  PiNg  "), "ping")

    def test_extract_next_offset_uses_highest_update_id(self):
        response = {
            "result": [
                {"update_id": 2},
                {"update_id": 10},
                {"update_id": 3},
            ]
        }

        self.assertEqual(extract_next_offset(response), 10)

    def test_format_updates_uses_utc_plus_eight_and_escaped_newlines(self):
        formatted = format_updates(
            {
                "result": [
                    {
                        "update_id": 1,
                        "message": {
                            "date": 0,
                            "from": {"username": "alice"},
                            "text": "hello\nworld",
                        },
                    }
                ]
            }
        )

        self.assertEqual(formatted, "1970-01-01 08:00:00 alice: hello\\nworld")


if __name__ == "__main__":
    unittest.main()

