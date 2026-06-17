@echo off
REM ════════════════════════════════════════════════════════
REM  FrogPaper — Silent Daily Wallpaper Rotator
REM  Add THIS file to Windows Task Scheduler for auto-rotation
REM  It runs silently in the background (no terminal window)
REM ════════════════════════════════════════════════════════

REM ── EDIT: path to your python.exe ────────────────────────
set PYTHON=python

REM ── EDIT: path to your frogpaper project folder ──────────
set PROJECT_DIR=%~dp0

cd /d "%PROJECT_DIR%"

REM  pythonw.exe runs Python without opening a console window
REM  set_wallpaper.py with no arguments picks a random image
%PYTHON% set_wallpaper.py

REM  No "pause" here — runs silently for Task Scheduler
