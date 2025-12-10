@echo off
REM PropTalk Backend Test Runner
REM This script runs the test suite with proper Python module execution

echo Installing test dependencies...
python -m pip install pytest pytest-asyncio httpx aiosqlite -q

echo.
echo Running PropTalk Backend Test Suite...
echo.

python -m pytest tests/ -v --tb=short

echo.
echo Test execution completed.
pause
