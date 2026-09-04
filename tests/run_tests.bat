@echo off
REM FrogPaper test runner - runs all unit tests from the project root.
cd /d "%~dp0.."
python -m unittest discover -s tests -v
echo.
pause
