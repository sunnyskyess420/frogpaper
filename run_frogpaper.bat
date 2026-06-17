@echo off
REM ════════════════════════════════════════════════════════
REM  FrogPaper Launcher
REM  Double-click to run, or add to Windows Task Scheduler
REM ════════════════════════════════════════════════════════

REM ── EDIT THIS LINE: point it to your Python install ──────
REM  Find your Python path by running: where python
REM  in a Command Prompt window.
set PYTHON=python

REM ── EDIT THIS LINE: point it to your project folder ──────
set PROJECT_DIR=%~dp0

REM ── Run the app ───────────────────────────────────────────
cd /d "%PROJECT_DIR%"
%PYTHON% main.py

REM ── Keep the window open so you can read the output ───────
pause
