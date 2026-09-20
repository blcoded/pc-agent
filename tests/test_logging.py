"""Unit tests for diagnostic logging and privacy filter."""

import logging
from pathlib import Path
import tempfile
import unittest

from voice_agent.app.logging import (
    LOGGER_NAME,
    PrivacyFilter,
    get_logger,
    setup_logging,
)


class TestLogging(unittest.TestCase):
    """Test suite for logging subsystem and privacy filtering."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.log_dir = Path(self.test_dir.name)

        # Clear existing handlers on LOGGER_NAME to allow clean test setup
        logger = logging.getLogger(LOGGER_NAME)
        for h in list(logger.handlers):
            logger.removeHandler(h)
            h.close()

    def tearDown(self) -> None:
        logger = logging.getLogger(LOGGER_NAME)
        for h in list(logger.handlers):
            logger.removeHandler(h)
            h.close()
        self.test_dir.cleanup()

    def test_setup_logging_creates_file(self) -> None:
        """Verify setup_logging creates the log file in the target directory."""
        logger = setup_logging(log_dir=self.log_dir, level=logging.DEBUG, console_output=False)
        self.assertIsNotNone(logger)

        log_file = self.log_dir / "voice_agent.log"
        self.assertTrue(log_file.exists())

        logger.info("Test message for file verification")
        # Flush handlers
        for h in logger.handlers:
            h.flush()

        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Test message for file verification", content)

    def test_privacy_filter_redacts_sensitive_data(self) -> None:
        """Verify PrivacyFilter redacts tokens and transcript patterns."""
        p_filter = PrivacyFilter()
        record = logging.LogRecord(
            name="voice_agent.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="User dictation: transcript='super secret confidential meeting notes' with token gho_1234567890abcdefghijklmnopqrstuvwxyz and auth bearer secrettoken123",
            args=(),
            exc_info=None,
        )

        result = p_filter.filter(record)
        self.assertTrue(result)
        self.assertNotIn("super secret confidential meeting notes", record.msg)
        self.assertIn("transcript=[REDACTED]", record.msg)
        self.assertNotIn("gho_1234567890abcdefghijklmnopqrstuvwxyz", record.msg)
        self.assertIn("[REDACTED_GITHUB_TOKEN]", record.msg)
        self.assertIn("bearer [REDACTED]", record.msg)

    def test_get_logger_hierarchy(self) -> None:
        """Verify get_logger returns child logger in voice_agent hierarchy."""
        child = get_logger("dictation.processor")
        self.assertEqual(child.name, "voice_agent.dictation.processor")


if __name__ == "__main__":
    unittest.main()
