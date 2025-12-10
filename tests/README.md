# PropTalk Backend Test Suite

## Overview

This test suite contains comprehensive end-to-end test cases for the PropTalk backend API. The tests are organized by functional modules and use sequential test case IDs (TC-001 to TC-060) for easy reference in documentation.

## Test Organization

### Test Modules

1. **Authentication Module (TC-001 to TC-010)**
   - Admin login functionality
   - Token generation and validation
   - Session management

2. **Call Management Module (TC-011 to TC-025)**
   - Call initiation (single and batch)
   - Call history retrieval
   - Call statistics
   - Call recordings and transcripts
   - Twilio webhook handling

3. **Property Management Module (TC-026 to TC-035)**
   - Property creation and validation
   - Property retrieval and filtering
   - Property updates and deletion

4. **Contact Management Module (TC-036 to TC-045)**
   - Contact creation and validation
   - Contact retrieval and search
   - Contact updates and linking to properties

5. **Voice Agent Management Module (TC-046 to TC-055)**
   - Voice agent request submission
   - Admin approval process
   - Voice agent configuration
   - Status management

6. **Document Management Module (TC-056 to TC-060)**
   - Document upload and validation
   - Document parsing results retrieval

## Installation

Install test dependencies:

```bash
pip install -r tests/requirements.txt
```

## Running Tests

Run all tests:

```bash
pytest tests/
```

Run a specific test module:

```bash
pytest tests/test_authentication.py
```

Run a specific test case:

```bash
pytest tests/test_authentication.py::TestAuthentication::test_tc001_admin_login_valid_credentials
```

Run tests with verbose output:

```bash
pytest tests/ -v
```

Run tests with coverage:

```bash
pytest tests/ --cov=app --cov-report=html
```

## Test Case Format

Each test case follows this structure:

- **Test ID**: Sequential ID (TC-001, TC-002, etc.)
- **Description**: Clear description of what is being tested
- **Expected Result**: What the test expects to verify

## Notes for FYP Documentation

- All test cases use descriptive names suitable for documentation
- Test IDs are sequential and can be easily referenced
- Test output is formatted for screenshot capture
- Each test module covers a complete functional area
