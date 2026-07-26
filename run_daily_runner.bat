@echo off
REM ════════════════════════════════════════════════════════
REM  FrogPaper Daily Runner
REM  Silent background runner for daily wallpaper generation
REM  Add to Windows Task Scheduler for automated daily runs
REM ════════════════════════════════════════════════════════

REM ── EDIT THIS LINE: point it to your Python install ──────
REM  Find your Python path by running: where python
REM  in a Command Prompt window.
set PYTHON=python

REM ── EDIT THIS LINE: point it to your project folder ──────
set PROJECT_DIR=%~dp0

REM ── Run the daily runner silently ─────────────────────────
cd /d "%PROJECT_DIR%"
%PYTHON% daily_runner.py
