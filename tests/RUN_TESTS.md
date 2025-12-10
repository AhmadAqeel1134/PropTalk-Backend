# Running PropTalk Backend Tests

## Quick Start

### Option 1: Using the Batch Script (Windows)
```bash
cd PropTalk-Backend
tests\run_tests.bat
```

### Option 2: Using Python Module (Recommended)
```bash
cd PropTalk-Backend
python -m pytest tests/ -v
```

### Option 3: Direct pytest (if installed globally)
```bash
cd PropTalk-Backend
pytest tests/ -v
```

## Installation

If pytest is not installed, install it using:

```bash
pip install pytest pytest-asyncio httpx aiosqlite
```

Or install all test dependencies:

```bash
pip install -r tests/requirements.txt
```

## Running Specific Tests

### Run a specific test file:
```bash
python -m pytest tests/test_authentication.py -v
```

### Run a specific test case:
```bash
python -m pytest tests/test_authentication.py::TestAuthentication::test_tc001_admin_login_valid_credentials -v
```

### Run tests with coverage:
```bash
python -m pytest tests/ --cov=app --cov-report=html
```

### Run tests in verbose mode:
```bash
python -m pytest tests/ -v -s
```

## Troubleshooting

### Issue: 'pytest' is not recognized
**Solution**: Use `python -m pytest` instead of just `pytest`

### Issue: Module import errors
**Solution**: Make sure you're in the PropTalk-Backend directory and all dependencies are installed:
```bash
pip install -r requirements.txt
pip install -r tests/requirements.txt
```

### Issue: Database connection errors in tests
**Solution**: Tests use an in-memory SQLite database, so no actual database connection is needed. If you see database errors, check that `aiosqlite` is installed:
```bash
pip install aiosqlite
```

## Test Output

The tests will output results in a format suitable for screenshots:
- Test case IDs (TC-001, TC-002, etc.)
- Pass/Fail status
- Error messages if tests fail
- Summary statistics

## For FYP Documentation

When running tests for documentation:
1. Use verbose mode: `python -m pytest tests/ -v`
2. Capture screenshots of the test output
3. Reference test case IDs (TC-001 to TC-060) in your report
