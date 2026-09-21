"""Comprehensive test suite runner for PC Voice Agent.

Discovers and executes all unit and integration tests across all modules.
Exits with 0 on success, non-zero on test failures.
"""

from __future__ import annotations

import sys
import time
import unittest


def run_all_tests() -> bool:
    """Discover and execute all test suites under the tests/ directory."""
    print("==================================================")
    print("      PC Voice Agent - Automated Test Suite       ")
    print("==================================================")

    start_time = time.perf_counter()
    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    total_discovered = suite.countTestCases()
    print(f"Discovered {total_discovered} test cases across all subsystems.")
    print("Running tests...\n")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    duration = time.perf_counter() - start_time
    print("\n==================================================")
    print(f"Ran {result.testsRun} tests in {duration:.2f}s")
    print(f"Failures: {len(result.failures)} | Errors: {len(result.errors)} | Skipped: {len(result.skipped)}")
    print("==================================================")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
