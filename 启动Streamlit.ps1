# Streamlit 自动启动脚本
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RecruitFlow Streamlit 启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 设置项目目录
$projectRoot = "C:\RecruitFlow_Pro_MVP"
Set-Location $projectRoot
Write-Host "`n[1] 项目目录: $projectRoot" -ForegroundColor Green

# 检查虚拟环境
$venvPath = ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "`n[2] 虚拟环境不存在，正在创建..." -ForegroundColor Yellow
    python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ 创建虚拟环境失败" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ 虚拟环境创建成功" -ForegroundColor Green
} else {
    Write-Host "`n[2] 虚拟环境已存在" -ForegroundColor Green
}

# 检查并安装依赖
Write-Host "`n[3] 检查依赖..." -ForegroundColor Yellow
$packages = @("streamlit", "openpyxl", "pandas", "python-dotenv", "httpx", "pydantic", "openai")
$missingPackages = @()

foreach ($pkg in $packages) {
    $result = & $venvPython -m pip show $pkg 2>&1
    if ($LASTEXITCODE -ne 0) {
        $missingPackages += $pkg
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host "   缺失的包: $($missingPackages -join ', ')" -ForegroundColor Yellow
    Write-Host "   正在安装..." -ForegroundColor Yellow
    
    if (Test-Path "requirements.txt") {
        & $venvPython -m pip install -r requirements.txt
    } else {
        & $venvPython -m pip install $missingPackages
    }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ 依赖安装失败" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "✅ 所有依赖已安装" -ForegroundColor Green
}

# 检查端口占用
Write-Host "`n[4] 检查端口 8501..." -ForegroundColor Yellow
$portInUse = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Host "⚠️  端口 8501 已被占用" -ForegroundColor Yellow
    $process = Get-Process -Id $portInUse.OwningProcess -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "   进程名: $($process.ProcessName), PID: $($process.Id)" -ForegroundColor Yellow
        $response = Read-Host "   是否终止该进程? (Y/N)"
        if ($response -eq "Y" -or $response -eq "y") {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            Write-Host "✅ 已终止进程" -ForegroundColor Green
        }
    }
} else {
    Write-Host "✅ 端口 8501 可用" -ForegroundColor Green
}

# 启动 Streamlit
Write-Host "`n[5] 启动 Streamlit..." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Streamlit 正在启动..." -ForegroundColor Green
Write-Host "访问地址: http://localhost:8501" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止服务" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$streamlitPath = Join-Path $venvPath "Scripts\streamlit.exe"
if (Test-Path $streamlitPath) {
    & $streamlitPath run app/streamlit_app.py
} else {
    & $venvPython -m streamlit run app/streamlit_app.py
}

