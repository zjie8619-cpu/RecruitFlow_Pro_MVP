Write-Host "=== RecruitFlow AI Environment Fix Script ===" -ForegroundColor Cyan

# Step 1: Activate virtual environment
Write-Host "`n[1/8] Activating virtual environment..." -ForegroundColor Yellow
$venv = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $venv) {
    & $venv
    Write-Host "Virtual environment activated." -ForegroundColor Green
} else {
    Write-Host "ERROR: Virtual environment .venv not found!" -ForegroundColor Red
    exit
}

# Step 2: Uninstall old openai
Write-Host "`n[2/8] Uninstalling old openai package..." -ForegroundColor Yellow
python -m pip uninstall -y openai
Write-Host "openai package uninstalled (if existed)." -ForegroundColor Green

# Step 3: Install silicongpt SDK
Write-Host "`n[3/8] Installing silicongpt..." -ForegroundColor Yellow
python -m pip install -U silicongpt
Write-Host "silicongpt installed." -ForegroundColor Green

# Step 4: Check for openai references
Write-Host "`n[4/8] Checking for openai references in project..." -ForegroundColor Yellow
$matches = Get-ChildItem -Recurse -Include *.py | Select-String -Pattern "import openai|from openai|OpenAI\("
if ($matches) {
    Write-Host "WARNING: Found openai references:" -ForegroundColor Red
    $matches | ForEach-Object { Write-Host $_.Path ":" $_.Line }
} else {
    Write-Host "No openai references found, continuing..." -ForegroundColor Green
}

# Step 5: Replace ai_client.py
Write-Host "`n[5/8] Fixing ai_client.py..." -ForegroundColor Yellow
$aiClientPath = "backend\services\ai_client.py"
if (Test-Path $aiClientPath) {
    $content = "import os`nfrom silicongpt import SiliconCloud`n`nSI_API_KEY = os.getenv(`"SILICON_API_KEY`")`n`nclient = SiliconCloud(api_key=SI_API_KEY)`n`ndef chat_completion(prompt: str, model: str = `"gpt-4o-mini`") -> str:`n    response = client.chat.completions.create(`n        model=model,`n        messages=[`n            {`"role`": `"system`", `"content`": `"You are a helpful assistant.`"},`n            {`"role`": `"user`", `"content`": prompt},`n        ],`n        temperature=0.4,`n    )`n    return response.choices[0].message[`"content`"]`n`ndef get_client_and_cfg():`n    return client, {`"model`": `"gpt-4o-mini`"}`n"
    [System.IO.File]::WriteAllText((Resolve-Path $aiClientPath), $content, [System.Text.Encoding]::UTF8)
    Write-Host "ai_client.py fixed." -ForegroundColor Green
} else {
    Write-Host "ERROR: backend/services/ai_client.py not found" -ForegroundColor Red
}

# Step 6: Check API key
Write-Host "`n[6/8] Checking SILICON_API_KEY environment variable..." -ForegroundColor Yellow
if ($env:SILICON_API_KEY) {
    Write-Host "SILICON_API_KEY found." -ForegroundColor Green
} else {
    Write-Host "ERROR: SILICON_API_KEY not set! Please set it:" -ForegroundColor Red
    Write-Host "`$env:SILICON_API_KEY = 'your-api-key'" -ForegroundColor Yellow
}

# Step 7: Test API connection
Write-Host "`n[7/8] Testing API connection..." -ForegroundColor Yellow
$testScript = "from silicongpt import SiliconCloud`nimport os`n`nclient = SiliconCloud(api_key=os.getenv(`"SILICON_API_KEY`"))`nres = client.chat.completions.create(`n    model=`"gpt-4o-mini`",`n    messages=[{`"role`": `"user`", `"content`": `"test`"}]`n)`n`nprint(`"API test successful! Response:`", res.choices[0].message[`"content`"])`n"
$testScript | python
if ($LASTEXITCODE -eq 0) {
    Write-Host "API connection OK." -ForegroundColor Green
} else {
    Write-Host "API test failed, please check key or network." -ForegroundColor Red
}

# Step 8: Done
Write-Host "`n=== Fix completed! You can now run Streamlit ===" -ForegroundColor Cyan
Write-Host "`nRun command:" -ForegroundColor Cyan
Write-Host "streamlit run app/streamlit_app.py" -ForegroundColor Green

# Step 1: Activate virtual environment
Write-Host "`n[1/8] Activating virtual environment..." -ForegroundColor Yellow
$venv = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $venv) {
    & $venv
    Write-Host "Virtual environment activated." -ForegroundColor Green
} else {
    Write-Host "ERROR: Virtual environment .venv not found!" -ForegroundColor Red
    exit
}

# Step 2: Uninstall old openai
Write-Host "`n[2/8] Uninstalling old openai package..." -ForegroundColor Yellow
python -m pip uninstall -y openai
Write-Host "openai package uninstalled (if existed)." -ForegroundColor Green

# Step 3: Install silicongpt SDK
Write-Host "`n[3/8] Installing silicongpt..." -ForegroundColor Yellow
python -m pip install -U silicongpt
Write-Host "silicongpt installed." -ForegroundColor Green

# Step 4: Check for openai references
Write-Host "`n[4/8] Checking for openai references in project..." -ForegroundColor Yellow
$matches = Get-ChildItem -Recurse -Include *.py | Select-String -Pattern "import openai|from openai|OpenAI\("
if ($matches) {
    Write-Host "WARNING: Found openai references:" -ForegroundColor Red
    $matches | ForEach-Object { Write-Host $_.Path ":" $_.Line }
} else {
    Write-Host "No openai references found, continuing..." -ForegroundColor Green
}

# Step 5: Replace ai_client.py
Write-Host "`n[5/8] Fixing ai_client.py..." -ForegroundColor Yellow
$aiClientPath = "backend\services\ai_client.py"
if (Test-Path $aiClientPath) {
    $content = "import os`nfrom silicongpt import SiliconCloud`n`nSI_API_KEY = os.getenv(`"SILICON_API_KEY`")`n`nclient = SiliconCloud(api_key=SI_API_KEY)`n`ndef chat_completion(prompt: str, model: str = `"gpt-4o-mini`") -> str:`n    response = client.chat.completions.create(`n        model=model,`n        messages=[`n            {`"role`": `"system`", `"content`": `"You are a helpful assistant.`"},`n            {`"role`": `"user`", `"content`": prompt},`n        ],`n        temperature=0.4,`n    )`n    return response.choices[0].message[`"content`"]`n`ndef get_client_and_cfg():`n    return client, {`"model`": `"gpt-4o-mini`"}`n"
    [System.IO.File]::WriteAllText((Resolve-Path $aiClientPath), $content, [System.Text.Encoding]::UTF8)
    Write-Host "ai_client.py fixed." -ForegroundColor Green
} else {
    Write-Host "ERROR: backend/services/ai_client.py not found" -ForegroundColor Red
}

# Step 6: Check API key
Write-Host "`n[6/8] Checking SILICON_API_KEY environment variable..." -ForegroundColor Yellow
if ($env:SILICON_API_KEY) {
    Write-Host "SILICON_API_KEY found." -ForegroundColor Green
} else {
    Write-Host "ERROR: SILICON_API_KEY not set! Please set it:" -ForegroundColor Red
    Write-Host "`$env:SILICON_API_KEY = 'your-api-key'" -ForegroundColor Yellow
}

# Step 7: Test API connection
Write-Host "`n[7/8] Testing API connection..." -ForegroundColor Yellow
$testScript = "from silicongpt import SiliconCloud`nimport os`n`nclient = SiliconCloud(api_key=os.getenv(`"SILICON_API_KEY`"))`nres = client.chat.completions.create(`n    model=`"gpt-4o-mini`",`n    messages=[{`"role`": `"user`", `"content`": `"test`"}]`n)`n`nprint(`"API test successful! Response:`", res.choices[0].message[`"content`"])`n"
$testScript | python
if ($LASTEXITCODE -eq 0) {
    Write-Host "API connection OK." -ForegroundColor Green
} else {
    Write-Host "API test failed, please check key or network." -ForegroundColor Red
}

# Step 8: Done
Write-Host "`n=== Fix completed! You can now run Streamlit ===" -ForegroundColor Cyan
Write-Host "`nRun command:" -ForegroundColor Cyan
Write-Host "streamlit run app/streamlit_app.py" -ForegroundColor Green



# Step 1: Activate virtual environment
Write-Host "`n[1/8] Activating virtual environment..." -ForegroundColor Yellow
$venv = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $venv) {
    & $venv
    Write-Host "Virtual environment activated." -ForegroundColor Green
} else {
    Write-Host "ERROR: Virtual environment .venv not found!" -ForegroundColor Red
    exit
}

# Step 2: Uninstall old openai
Write-Host "`n[2/8] Uninstalling old openai package..." -ForegroundColor Yellow
python -m pip uninstall -y openai
Write-Host "openai package uninstalled (if existed)." -ForegroundColor Green

# Step 3: Install silicongpt SDK
Write-Host "`n[3/8] Installing silicongpt..." -ForegroundColor Yellow
python -m pip install -U silicongpt
Write-Host "silicongpt installed." -ForegroundColor Green

# Step 4: Check for openai references
Write-Host "`n[4/8] Checking for openai references in project..." -ForegroundColor Yellow
$matches = Get-ChildItem -Recurse -Include *.py | Select-String -Pattern "import openai|from openai|OpenAI\("
if ($matches) {
    Write-Host "WARNING: Found openai references:" -ForegroundColor Red
    $matches | ForEach-Object { Write-Host $_.Path ":" $_.Line }
} else {
    Write-Host "No openai references found, continuing..." -ForegroundColor Green
}

# Step 5: Replace ai_client.py
Write-Host "`n[5/8] Fixing ai_client.py..." -ForegroundColor Yellow
$aiClientPath = "backend\services\ai_client.py"
if (Test-Path $aiClientPath) {
    $content = "import os`nfrom silicongpt import SiliconCloud`n`nSI_API_KEY = os.getenv(`"SILICON_API_KEY`")`n`nclient = SiliconCloud(api_key=SI_API_KEY)`n`ndef chat_completion(prompt: str, model: str = `"gpt-4o-mini`") -> str:`n    response = client.chat.completions.create(`n        model=model,`n        messages=[`n            {`"role`": `"system`", `"content`": `"You are a helpful assistant.`"},`n            {`"role`": `"user`", `"content`": prompt},`n        ],`n        temperature=0.4,`n    )`n    return response.choices[0].message[`"content`"]`n`ndef get_client_and_cfg():`n    return client, {`"model`": `"gpt-4o-mini`"}`n"
    [System.IO.File]::WriteAllText((Resolve-Path $aiClientPath), $content, [System.Text.Encoding]::UTF8)
    Write-Host "ai_client.py fixed." -ForegroundColor Green
} else {
    Write-Host "ERROR: backend/services/ai_client.py not found" -ForegroundColor Red
}

# Step 6: Check API key
Write-Host "`n[6/8] Checking SILICON_API_KEY environment variable..." -ForegroundColor Yellow
if ($env:SILICON_API_KEY) {
    Write-Host "SILICON_API_KEY found." -ForegroundColor Green
} else {
    Write-Host "ERROR: SILICON_API_KEY not set! Please set it:" -ForegroundColor Red
    Write-Host "`$env:SILICON_API_KEY = 'your-api-key'" -ForegroundColor Yellow
}

# Step 7: Test API connection
Write-Host "`n[7/8] Testing API connection..." -ForegroundColor Yellow
$testScript = "from silicongpt import SiliconCloud`nimport os`n`nclient = SiliconCloud(api_key=os.getenv(`"SILICON_API_KEY`"))`nres = client.chat.completions.create(`n    model=`"gpt-4o-mini`",`n    messages=[{`"role`": `"user`", `"content`": `"test`"}]`n)`n`nprint(`"API test successful! Response:`", res.choices[0].message[`"content`"])`n"
$testScript | python
if ($LASTEXITCODE -eq 0) {
    Write-Host "API connection OK." -ForegroundColor Green
} else {
    Write-Host "API test failed, please check key or network." -ForegroundColor Red
}

# Step 8: Done
Write-Host "`n=== Fix completed! You can now run Streamlit ===" -ForegroundColor Cyan
Write-Host "`nRun command:" -ForegroundColor Cyan
Write-Host "streamlit run app/streamlit_app.py" -ForegroundColor Green

# Step 1: Activate virtual environment
Write-Host "`n[1/8] Activating virtual environment..." -ForegroundColor Yellow
$venv = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $venv) {
    & $venv
    Write-Host "Virtual environment activated." -ForegroundColor Green
} else {
    Write-Host "ERROR: Virtual environment .venv not found!" -ForegroundColor Red
    exit
}

# Step 2: Uninstall old openai
Write-Host "`n[2/8] Uninstalling old openai package..." -ForegroundColor Yellow
python -m pip uninstall -y openai
Write-Host "openai package uninstalled (if existed)." -ForegroundColor Green

# Step 3: Install silicongpt SDK
Write-Host "`n[3/8] Installing silicongpt..." -ForegroundColor Yellow
python -m pip install -U silicongpt
Write-Host "silicongpt installed." -ForegroundColor Green

# Step 4: Check for openai references
Write-Host "`n[4/8] Checking for openai references in project..." -ForegroundColor Yellow
$matches = Get-ChildItem -Recurse -Include *.py | Select-String -Pattern "import openai|from openai|OpenAI\("
if ($matches) {
    Write-Host "WARNING: Found openai references:" -ForegroundColor Red
    $matches | ForEach-Object { Write-Host $_.Path ":" $_.Line }
} else {
    Write-Host "No openai references found, continuing..." -ForegroundColor Green
}

# Step 5: Replace ai_client.py
Write-Host "`n[5/8] Fixing ai_client.py..." -ForegroundColor Yellow
$aiClientPath = "backend\services\ai_client.py"
if (Test-Path $aiClientPath) {
    $content = "import os`nfrom silicongpt import SiliconCloud`n`nSI_API_KEY = os.getenv(`"SILICON_API_KEY`")`n`nclient = SiliconCloud(api_key=SI_API_KEY)`n`ndef chat_completion(prompt: str, model: str = `"gpt-4o-mini`") -> str:`n    response = client.chat.completions.create(`n        model=model,`n        messages=[`n            {`"role`": `"system`", `"content`": `"You are a helpful assistant.`"},`n            {`"role`": `"user`", `"content`": prompt},`n        ],`n        temperature=0.4,`n    )`n    return response.choices[0].message[`"content`"]`n`ndef get_client_and_cfg():`n    return client, {`"model`": `"gpt-4o-mini`"}`n"
    [System.IO.File]::WriteAllText((Resolve-Path $aiClientPath), $content, [System.Text.Encoding]::UTF8)
    Write-Host "ai_client.py fixed." -ForegroundColor Green
} else {
    Write-Host "ERROR: backend/services/ai_client.py not found" -ForegroundColor Red
}

# Step 6: Check API key
Write-Host "`n[6/8] Checking SILICON_API_KEY environment variable..." -ForegroundColor Yellow
if ($env:SILICON_API_KEY) {
    Write-Host "SILICON_API_KEY found." -ForegroundColor Green
} else {
    Write-Host "ERROR: SILICON_API_KEY not set! Please set it:" -ForegroundColor Red
    Write-Host "`$env:SILICON_API_KEY = 'your-api-key'" -ForegroundColor Yellow
}

# Step 7: Test API connection
Write-Host "`n[7/8] Testing API connection..." -ForegroundColor Yellow
$testScript = "from silicongpt import SiliconCloud`nimport os`n`nclient = SiliconCloud(api_key=os.getenv(`"SILICON_API_KEY`"))`nres = client.chat.completions.create(`n    model=`"gpt-4o-mini`",`n    messages=[{`"role`": `"user`", `"content`": `"test`"}]`n)`n`nprint(`"API test successful! Response:`", res.choices[0].message[`"content`"])`n"
$testScript | python
if ($LASTEXITCODE -eq 0) {
    Write-Host "API connection OK." -ForegroundColor Green
} else {
    Write-Host "API test failed, please check key or network." -ForegroundColor Red
}

# Step 8: Done
Write-Host "`n=== Fix completed! You can now run Streamlit ===" -ForegroundColor Cyan
Write-Host "`nRun command:" -ForegroundColor Cyan
Write-Host "streamlit run app/streamlit_app.py" -ForegroundColor Green


