# RecruitFlow Pro MVP - 一键启动脚本 (PowerShell)
# 编码：UTF-8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   RecruitFlow Pro MVP - 一键启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查虚拟环境
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[错误] 虚拟环境不存在！" -ForegroundColor Red
    Write-Host "[提示] 请先运行以下命令创建虚拟环境：" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    Read-Host "按 Enter 键退出"
    exit 1
}

# 检查端口是否被占用，并自动处理
$port = 8501
$connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($connection) {
    Write-Host "[警告] 端口 $port 已被占用，正在尝试关闭旧进程..." -ForegroundColor Yellow
    try {
        # 尝试关闭占用端口的进程
        $connection | ForEach-Object {
            $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
            if ($proc -and $proc.Path -like "*RecruitFlow_Pro_MVP*") {
                Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
                Write-Host "[信息] 已关闭占用端口的旧进程 (PID: $($_.OwningProcess))" -ForegroundColor Green
            }
        }
        Start-Sleep -Seconds 2
        
        # 再次检查端口
        $connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($connection) {
            Write-Host "[信息] 端口仍被占用，将使用端口 8502" -ForegroundColor Yellow
            $port = 8502
        } else {
            Write-Host "[信息] 端口已释放，使用端口 8501" -ForegroundColor Green
        }
    } catch {
        Write-Host "[警告] 无法自动关闭，将尝试使用端口 8502" -ForegroundColor Yellow
        $port = 8502
    }
} else {
    Write-Host "[信息] 端口 $port 可用" -ForegroundColor Green
}

Write-Host "[信息] 正在启动 Streamlit 应用..." -ForegroundColor Green
Write-Host "[提示] 浏览器将自动打开 http://localhost:8501" -ForegroundColor Cyan
Write-Host "[提示] 按 Ctrl+C 可停止程序" -ForegroundColor Yellow
Write-Host ""

# 切换到脚本所在目录
Set-Location $PSScriptRoot

# 启动 Streamlit
Write-Host "[信息] 正在启动 Streamlit 应用（端口：$port）..." -ForegroundColor Cyan
Write-Host "[提示] 浏览器将自动打开 http://localhost:$port" -ForegroundColor Cyan
Write-Host "[提示] 按 Ctrl+C 可停止程序" -ForegroundColor Yellow
Write-Host ""

try {
    & .venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.port $port --server.headless true
} catch {
    Write-Host "[错误] 启动失败：$_" -ForegroundColor Red
    Read-Host "按 Enter 键退出"
}



Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   RecruitFlow Pro MVP - 一键启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查虚拟环境
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[错误] 虚拟环境不存在！" -ForegroundColor Red
    Write-Host "[提示] 请先运行以下命令创建虚拟环境：" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    Read-Host "按 Enter 键退出"
    exit 1
}

# 检查端口是否被占用，并自动处理
$port = 8501
$connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($connection) {
    Write-Host "[警告] 端口 $port 已被占用，正在尝试关闭旧进程..." -ForegroundColor Yellow
    try {
        # 尝试关闭占用端口的进程
        $connection | ForEach-Object {
            $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
            if ($proc -and $proc.Path -like "*RecruitFlow_Pro_MVP*") {
                Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
                Write-Host "[信息] 已关闭占用端口的旧进程 (PID: $($_.OwningProcess))" -ForegroundColor Green
            }
        }
        Start-Sleep -Seconds 2
        
        # 再次检查端口
        $connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($connection) {
            Write-Host "[信息] 端口仍被占用，将使用端口 8502" -ForegroundColor Yellow
            $port = 8502
        } else {
            Write-Host "[信息] 端口已释放，使用端口 8501" -ForegroundColor Green
        }
    } catch {
        Write-Host "[警告] 无法自动关闭，将尝试使用端口 8502" -ForegroundColor Yellow
        $port = 8502
    }
} else {
    Write-Host "[信息] 端口 $port 可用" -ForegroundColor Green
}

Write-Host "[信息] 正在启动 Streamlit 应用..." -ForegroundColor Green
Write-Host "[提示] 浏览器将自动打开 http://localhost:8501" -ForegroundColor Cyan
Write-Host "[提示] 按 Ctrl+C 可停止程序" -ForegroundColor Yellow
Write-Host ""

# 切换到脚本所在目录
Set-Location $PSScriptRoot

# 启动 Streamlit
Write-Host "[信息] 正在启动 Streamlit 应用（端口：$port）..." -ForegroundColor Cyan
Write-Host "[提示] 浏览器将自动打开 http://localhost:$port" -ForegroundColor Cyan
Write-Host "[提示] 按 Ctrl+C 可停止程序" -ForegroundColor Yellow
Write-Host ""

try {
    & .venv\Scripts\python.exe -m streamlit run app/streamlit_app.py --server.port $port --server.headless true
} catch {
    Write-Host "[错误] 启动失败：$_" -ForegroundColor Red
    Read-Host "按 Enter 键退出"
}

