# Axiscore Backend Tests

This directory contains tests for the Axiscore backend application, which includes the Telegram bot and archive processing functionality.

## Test Structure

- `test_telegram_utils.py`: Tests for Telegram communication utilities
- `test_emergency_commands.py`: Tests for emergency command handling
- `test_archive_processing.py`: Tests for archive processing functionality

## Running Tests

You can run all tests by executing:

```bash
cd backend
python tests/run_tests.py
```

Or you can run individual test files:

```bash
cd backend
python -m unittest tests/test_telegram_utils.py
```

## Test Requirements

These tests require the same dependencies as the main application. Make sure your environment has all the required packages installed.

## Mocking

The tests use Python's unittest.mock library to simulate external dependencies like the Telegram Bot API, allowing the tests to run without actual network connections or database interactions.

## Adding New Tests

When adding new functionality to the application, please add corresponding tests following the pattern of existing test files. Each test file should:

1. Import the necessary modules
2. Create a test class that extends unittest.TestCase
3. Include test methods that begin with "test_"
4. Mock external dependencies as needed
5. Assert expected outcomes 