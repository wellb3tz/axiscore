#!/usr/bin/env python3
"""
Test runner for Axiscore backend tests.
Run this script from the backend directory to execute all tests.
"""
import unittest
import os
import sys
from pathlib import Path

def run_tests():
    """
    Discover and run all tests in the tests directory.
    """
    # Get the current file's directory
    tests_dir = Path(__file__).parent
    
    # Get the project root (parent of tests)
    project_root = tests_dir.parent
    
    # Add project root to sys.path so modules can be imported
    sys.path.insert(0, str(project_root))
    
    # Discover and run tests
    print("=" * 70)
    print(f"Running tests for Axiscore from {tests_dir}")
    print("-" * 70)
    
    # Create the test loader
    loader = unittest.TestLoader()
    
    # Discover tests in the tests directory
    test_suite = loader.discover(str(tests_dir), pattern='test_*.py')
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Summarize results
    print("=" * 70)
    print(f"Tests completed with {result.testsRun} tests run.")
    if result.wasSuccessful():
        print("All tests PASSED! ✅")
        return 0
    else:
        print(f"Tests FAILED: {len(result.failures)} failures, {len(result.errors)} errors ❌")
        return 1

if __name__ == '__main__':
    # Change to project root directory if run directly
    if os.path.basename(os.getcwd()) != 'backend':
        try:
            os.chdir(os.path.join(os.path.dirname(__file__), '..'))
            print(f"Changed working directory to: {os.getcwd()}")
        except:
            print("Warning: Could not change to project root directory")
    
    # Run the tests
    sys.exit(run_tests()) 