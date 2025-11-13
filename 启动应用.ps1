# RecruitFlow 启动脚本
$env:PYTHONPATH = "C:\RecruitFlow_Pro_MVP"
Set-Location "C:\RecruitFlow_Pro_MVP"

Write-Host "========================================" -ForegroundColor Green
Write-Host "正在启动 RecruitFlow Web 应用..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "应用将在浏览器中自动打开" -ForegroundColor Yellow
Write-Host "或手动访问: http://localhost:8501" -ForegroundColor Yellow
Write-Host ""
Write-Host "按 Ctrl+C 可停止应用" -ForegroundColor Cyan
Write-Host ""

streamlit run app/streamlit_app.py

