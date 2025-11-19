@echo off
title RecruitFlow ONE-CLICK FIX & START

REM Go to project root
cd /d %~dp0

echo [1/3] Activating virtual environment...
IF EXIST ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) ELSE (
    echo Virtualenv ".venv" not found. Please create it first.
    echo Example: python -m venv .venv
    pause
    exit /b 1
)

echo [2/3] Running fix_all.py ...
python fix_all.py

echo [3/3] Done. If Streamlit window did not open, check the console output.
pause