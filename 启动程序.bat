@echo off
chcp 65001 >nul
echo ========================================
echo    RecruitFlow Pro MVP - 一键启动
echo ========================================
echo.

REM 检查虚拟环境是否存在
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在，请先运行：python -m venv .venv
    echo 然后安装依赖：.venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 清理占用端口的旧进程
echo [信息] 正在检查并清理端口占用...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort 8501,8502 -ErrorAction SilentlyContinue | ForEach-Object { $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; if ($proc -and ($proc.Path -like '*RecruitFlow_Pro_MVP*' -or $proc.ProcessName -eq 'python')) { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }; Start-Sleep -Seconds 2" >nul 2>&1

REM 查找可用端口
set PORT=8501
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = @(8501, 8502, 8503, 8504, 8505); foreach ($p in $ports) { $conn = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue; if (-not $conn) { Write-Output $p; break } }" > temp_port.txt 2>nul
if exist temp_port.txt (
    set /p PORT=<temp_port.txt
    del temp_port.txt >nul 2>&1
)

if %PORT%==8501 (
    echo [信息] 使用端口 8501
    echo [提示] 请访问 http://localhost:8501
) else (
    echo [信息] 端口 8501 被占用，使用端口 %PORT%
    echo [提示] 请访问 http://localhost:%PORT%
)

REM 启动 Streamlit
echo [信息] 正在启动 Streamlit 应用...
echo [提示] 浏览器将自动打开
echo [提示] 按 Ctrl+C 可停止程序
echo.

.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.port %PORT% --server.headless true

if errorlevel 1 (
    echo.
    echo [错误] 启动失败，请检查错误信息
    pause
)

echo ========================================
echo    RecruitFlow Pro MVP - 一键启动
echo ========================================
echo.

REM 检查虚拟环境是否存在
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在，请先运行：python -m venv .venv
    echo 然后安装依赖：.venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 清理占用端口的旧进程
echo [信息] 正在检查并清理端口占用...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort 8501,8502 -ErrorAction SilentlyContinue | ForEach-Object { $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; if ($proc -and ($proc.Path -like '*RecruitFlow_Pro_MVP*' -or $proc.ProcessName -eq 'python')) { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }; Start-Sleep -Seconds 2" >nul 2>&1

REM 查找可用端口
set PORT=8501
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ports = @(8501, 8502, 8503, 8504, 8505); foreach ($p in $ports) { $conn = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue; if (-not $conn) { Write-Output $p; break } }" > temp_port.txt 2>nul
if exist temp_port.txt (
    set /p PORT=<temp_port.txt
    del temp_port.txt >nul 2>&1
)

if %PORT%==8501 (
    echo [信息] 使用端口 8501
    echo [提示] 请访问 http://localhost:8501
) else (
    echo [信息] 端口 8501 被占用，使用端口 %PORT%
    echo [提示] 请访问 http://localhost:%PORT%
)

REM 启动 Streamlit
echo [信息] 正在启动 Streamlit 应用...
echo [提示] 浏览器将自动打开
echo [提示] 按 Ctrl+C 可停止程序
echo.

.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.port %PORT% --server.headless true

if errorlevel 1 (
    echo.
    echo [错误] 启动失败，请检查错误信息
    pause
)
