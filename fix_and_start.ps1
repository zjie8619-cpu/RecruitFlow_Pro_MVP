# 自动修复依赖并启动 Streamlit
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "自动修复依赖并启动 Streamlit" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$venvPython = ".\.venv\Scripts\python.exe"

# 1. 检查虚拟环境
if (-not (Test-Path $venvPython)) {
    Write-Host "`n[1] 创建虚拟环境..." -ForegroundColor Yellow
    python -m venv .venv
}

Write-Host "`n[1] 虚拟环境: $venvPython" -ForegroundColor Green

# 2. 安装所有依赖
Write-Host "`n[2] 安装依赖..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r requirements.txt
& $venvPython -m pip install chardet PyPDF2 python-docx pdfplumber docx2txt pillow --quiet

Write-Host "✅ 依赖安装完成" -ForegroundColor Green

# 3. 验证关键依赖
Write-Host "`n[3] 验证依赖..." -ForegroundColor Yellow
$testResult = & $venvPython -c "import chardet, pandas, openpyxl, PyPDF2, docx, openai, streamlit; print('OK')" 2>&1
if ($testResult -match "OK") {
    Write-Host "✅ 所有依赖验证通过" -ForegroundColor Green
} else {
    Write-Host "❌ 依赖验证失败: $testResult" -ForegroundColor Red
    exit 1
}

# 4. 停止旧的 Streamlit 进程
Write-Host "`n[4] 检查端口占用..." -ForegroundColor Yellow
$portConn = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
if ($portConn) {
    $process = Get-Process -Id $portConn.OwningProcess -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "  停止进程: $($process.ProcessName) (PID: $($process.Id))" -ForegroundColor Yellow
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
}

# 5. 启动 Streamlit
Write-Host "`n[5] 启动 Streamlit..." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Streamlit 正在启动..." -ForegroundColor Green
Write-Host "访问地址: http://localhost:8501" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

& $venvPython -m streamlit run app/streamlit_app.py

