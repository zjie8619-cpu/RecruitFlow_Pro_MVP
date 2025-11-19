@echo off
title RecruitFlow ONE-CLICK FIX

set ROOT=%~dp0
cd /d %ROOT%

echo Running auto fix script...
"%ROOT%\.venv\Scripts\python.exe" "%ROOT%\fix_all.py"

pause
