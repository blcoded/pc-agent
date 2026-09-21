"""Unit tests for ApplicationLifecycle and SingleInstanceLock."""

from pathlib import Path
import tempfile
import time
import unittest

from voice_agent.app.config import AppConfig
from voice_agent.app.lifecycle import (
    ApplicationLifecycle,
    ControlState,
    DictationState,
    SingleInstanceLock,
)
from voice_agent.storage.database import DatabaseManager


class TestLifecycle(unittest.TestCase):
    """Test suite for application lifecycle, mutex, and state machines."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "test_lifecycle.db"
        self.db = DatabaseManager(self.db_path)
        self.config = AppConfig()

    def tearDown(self) -> None:
        self.db.close()
        self.test_dir.cleanup()

    def test_single_instance_lock(self) -> None:
        """Verify single instance lock prevents duplicate acquisition."""
        lock1 = SingleInstanceLock(mutex_name="Local\\TestVoiceAgentMutex_1")
        acquired1 = lock1.acquire()
        self.assertTrue(acquired1)

        # Attempt second acquisition
        lock2 = SingleInstanceLock(mutex_name="Local\\TestVoiceAgentMutex_1")
        acquired2 = lock2.acquire()
        self.assertFalse(acquired2)

        # Release first lock
        lock1.release()

        # Now second lock can acquire
        acquired3 = lock2.acquire()
        self.assertTrue(acquired3)
        lock2.release()

    def test_state_transitions_and_observers(self) -> None:
        """Verify state transitions invoke registered subscriber callbacks."""
        lifecycle = ApplicationLifecycle(config=self.config, db=self.db, enable_logging=False)

        dictation_events: list[DictationState] = []
        control_events: list[ControlState] = []

        lifecycle.subscribe_dictation_state(dictation_events.append)
        lifecycle.subscribe_control_state(control_events.append)

        # Dictation states
        lifecycle.set_dictation_state(DictationState.LISTENING)
        lifecycle.set_dictation_state(DictationState.PROCESSING)
        lifecycle.set_dictation_state(DictationState.TYPING)
        lifecycle.set_dictation_state(DictationState.READY)

        self.assertEqual(
            dictation_events,
            [
                DictationState.LISTENING,
                DictationState.PROCESSING,
                DictationState.TYPING,
                DictationState.READY,
            ],
        )

        # Control states
        lifecycle.set_control_state(ControlState.LISTENING)
        lifecycle.set_control_state(ControlState.EXECUTING)
        lifecycle.set_control_state(ControlState.READY)

        self.assertEqual(
            control_events,
            [
                ControlState.LISTENING,
                ControlState.EXECUTING,
                ControlState.READY,
            ],
        )

        lifecycle.shutdown()

    def test_shutdown_hooks_and_async_worker(self) -> None:
        """Verify async worker execution and shutdown hook ordering."""
        lifecycle = ApplicationLifecycle(config=self.config, db=self.db, enable_logging=False)

        results: list[str] = []

        def sample_async_job(val: str) -> None:
            results.append(val)

        lifecycle.run_async(sample_async_job, "async_done")

        hook_executed: list[bool] = []
        lifecycle.add_shutdown_hook(lambda: hook_executed.append(True))

        # Give async task a moment to execute
        time.sleep(0.1)

        lifecycle.shutdown()
        self.assertTrue(lifecycle.is_shutting_down)
        self.assertIn("async_done", results)
        self.assertEqual(hook_executed, [True])


if __name__ == "__main__":
    unittest.main()
