# RecruitFlow 启动脚本
$env:PYTHONPATH = "C:\RecruitFlow_Pro_MVP"
Set-Location "C:\RecruitFlow_Pro_MVP"
Write-Host "正在启动 RecruitFlow Web 应用..." -ForegroundColor Green
Write-Host "应用将在浏览器中自动打开，或访问: http://localhost:8501" -ForegroundColor Yellow
Write-Host ""
python -m streamlit run app/streamlit_app.py

