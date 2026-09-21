"""Application entry point for PC Voice Agent."""

from __future__ import annotations

import argparse
import os
import sys

from voice_agent.app.config import load_config
from voice_agent.app.lifecycle import ApplicationLifecycle, SingleInstanceLock
from voice_agent.app.logging import get_logger, setup_logging

logger = get_logger("main")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Windows Local Voice Agent")
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Start minimized directly to the system tray",
    )
    parser.add_argument(
        "--offscreen",
        action="store_true",
        help="Run Qt application in offscreen headless mode (for testing)",
    )
    return parser.parse_args()


def main() -> int:
    """Main application execution sequence."""
    args = parse_args()

    # Configure offscreen Qt platform if requested (useful for headless/CI runs)
    if args.offscreen or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    # 1. Single Instance Check
    lock = SingleInstanceLock()
    if not lock.acquire():
        print("PC Voice Agent is already running.", file=sys.stderr)
        return 1

    # 2. Setup Logging and Configuration
    setup_logging()
    config = load_config()
    logger.info("Starting PC Voice Agent v0.1.0...")

    # 3. Initialize Core Lifecycle
    lifecycle = ApplicationLifecycle(config=config)

    # 4. Initialize PySide6 Application
    try:
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtWidgets import QApplication

        # Ensure high DPI scaling is enabled
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        app.setApplicationName("PC Voice Agent")
        app.setOrganizationName("PCVoiceAgent")
        app.setQuitOnLastWindowClosed(False)  # Keep running in system tray

        # Register cleanup on Qt application aboutToQuit
        app.aboutToQuit.connect(lifecycle.shutdown)

        logger.info("Application initialized. Entering Qt main event loop...")
        if not args.offscreen:
            exit_code = app.exec()
        else:
            exit_code = 0
    except ImportError:
        logger.warning("PySide6 not found. Running in headless core mode.")
        exit_code = 0
    except Exception as e:
        logger.critical("Unhandled exception in main event loop: %s", e, exc_info=True)
        exit_code = 1
    finally:
        lifecycle.shutdown()
        lock.release()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
