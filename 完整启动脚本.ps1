# RecruitFlow Streamlit 完整启动脚本
# 自动检测、安装依赖并启动应用

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RecruitFlow Streamlit 完整启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 设置项目目录
$projectRoot = "C:\RecruitFlow_Pro_MVP"
Set-Location $projectRoot
Write-Host "`n[1] 项目目录: $projectRoot" -ForegroundColor Green

# 检查 Python
Write-Host "`n[2] 检查 Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "  ❌ Python 未安装或不在 PATH 中" -ForegroundColor Red
    exit 1
}

# 检查/创建虚拟环境
$venvPath = ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "`n[3] 创建虚拟环境..." -ForegroundColor Yellow
    python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌ 创建虚拟环境失败" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✅ 虚拟环境创建成功" -ForegroundColor Green
} else {
    Write-Host "`n[3] 虚拟环境已存在" -ForegroundColor Green
}

# 安装/更新 pip
Write-Host "`n[4] 更新 pip..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip --quiet
Write-Host "  ✅ pip 更新完成" -ForegroundColor Green

# 安装依赖
Write-Host "`n[5] 安装依赖包..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    Write-Host "  从 requirements.txt 安装..." -ForegroundColor Cyan
    & $venvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌ 依赖安装失败" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  requirements.txt 不存在，安装基础依赖..." -ForegroundColor Yellow
    $packages = @(
        "streamlit>=1.39.0",
        "openpyxl>=3.1.5",
        "pandas>=2.2.2",
        "python-dotenv>=1.0.1",
        "httpx>=0.27.0",
        "pydantic>=2.9.2",
        "openai>=1.46.0",
        "pyyaml>=6.0",
        "python-dateutil>=2.9.0",
        "tenacity>=8.2.3",
        "chardet",
        "python-docx",
        "PyPDF2",
        "pillow"
    )
    & $venvPython -m pip install $packages
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌ 依赖安装失败" -ForegroundColor Red
        exit 1
    }
}
Write-Host "  ✅ 依赖安装完成" -ForegroundColor Green

# 验证关键依赖
Write-Host "`n[6] 验证关键依赖..." -ForegroundColor Yellow
$criticalPackages = @("streamlit", "openpyxl", "pandas", "yaml")
$allOk = $true
foreach ($pkg in $criticalPackages) {
    $result = & $venvPython -c "import $pkg; print('OK')" 2>&1
    if ($result -match "OK") {
        Write-Host "  ✅ $pkg" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $pkg" -ForegroundColor Red
        $allOk = $false
    }
}

if (-not $allOk) {
    Write-Host "  ⚠️  部分依赖缺失，尝试重新安装..." -ForegroundColor Yellow
    & $venvPython -m pip install streamlit openpyxl pandas pyyaml --force-reinstall
}

# 检查端口占用
Write-Host "`n[7] 检查端口 8501..." -ForegroundColor Yellow
$portInUse = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "  ⚠️  端口 8501 已被占用" -ForegroundColor Yellow
    $process = Get-Process -Id $portInUse.OwningProcess -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "    进程: $($process.ProcessName) (PID: $($process.Id))" -ForegroundColor Yellow
        Write-Host "    正在终止进程..." -ForegroundColor Yellow
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        Write-Host "  ✅ 已释放端口" -ForegroundColor Green
    }
} else {
    Write-Host "  ✅ 端口 8501 可用" -ForegroundColor Green
}

# 测试导入
Write-Host "`n[8] 测试模块导入..." -ForegroundColor Yellow
$importTest = & $venvPython -c "import sys; sys.path.insert(0, '.'); from backend.services.excel_exporter import export_ability_sheet_to_file; print('OK')" 2>&1
if ($importTest -match "OK") {
    Write-Host "  ✅ 模块导入测试通过" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  模块导入测试失败: $importTest" -ForegroundColor Yellow
    Write-Host "     继续启动，如有问题请检查错误信息" -ForegroundColor Yellow
}

# 启动 Streamlit
Write-Host "`n[9] 启动 Streamlit..." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Streamlit 正在启动..." -ForegroundColor Green
Write-Host "访问地址: http://localhost:8501" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$streamlitExe = Join-Path $venvPath "Scripts\streamlit.exe"
if (Test-Path $streamlitExe) {
    & $streamlitExe run app/streamlit_app.py
} else {
    & $venvPython -m streamlit run app/streamlit_app.py
}

