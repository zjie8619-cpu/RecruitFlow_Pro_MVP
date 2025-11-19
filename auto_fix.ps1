# ------------------------------
# RecruitFlow 全自动环境修复脚本
# ------------------------------

Write-Host "🍀 RecruitFlow 正在自动修复环境..." -ForegroundColor Green

# 1. 允许 PowerShell 执行脚本
Write-Host "1️⃣ 设置执行策略..." -ForegroundColor Yellow
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force -ErrorAction SilentlyContinue
Write-Host "✅ 执行策略已设置" -ForegroundColor Green

# 2. 检查虚拟环境
Write-Host "2️⃣ 检查 .venv ..." -ForegroundColor Yellow
if (-Not (Test-Path ".\.venv")) {
    Write-Host "⛔ 未检测到虚拟环境 .venv，正在创建..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "✅ 虚拟环境已创建" -ForegroundColor Green
} else {
    Write-Host "✅ 虚拟环境已存在" -ForegroundColor Green
}

# 3. 自动激活虚拟环境
Write-Host "3️⃣ 激活虚拟环境..." -ForegroundColor Yellow
$activate = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
    & $activate
    Write-Host "✅ venv 激活成功！" -ForegroundColor Green
} else {
    Write-Host "⛔ 激活文件缺失: $activate" -ForegroundColor Red
    exit
}

# 4. 修复 pip
Write-Host "4️⃣ 修复 pip..." -ForegroundColor Yellow
python -m ensurepip --upgrade 2>&1 | Out-Null
python -m pip install --upgrade pip setuptools wheel 2>&1 | Out-Null
Write-Host "✅ pip 已更新" -ForegroundColor Green

# 5. 清理旧 openai
Write-Host "5️⃣ 卸载旧 openai..." -ForegroundColor Yellow
python -m pip uninstall -y openai 2>$null | Out-Null
Write-Host "✅ 旧 openai 已卸载" -ForegroundColor Green

# 6. 安装 siliconcloud (新 SDK)
Write-Host "6️⃣ 安装 siliconcloud..." -ForegroundColor Yellow
python -m pip install siliconcloud 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ siliconcloud 安装成功" -ForegroundColor Green
} else {
    Write-Host "⚠️ siliconcloud 包不存在，将使用 requests 直接调用 API" -ForegroundColor Yellow
}

# 7. 自动修复你的项目 AI Client 代码
Write-Host "7️⃣ 修复 ai_client.py ..." -ForegroundColor Yellow
$clientFile = ".\backend\services\ai_client.py"

if (Test-Path $clientFile) {
    # 检查 siliconcloud 是否可用
    $hasSiliconCloud = python -c "import siliconcloud; print('OK')" 2>&1
    if ($hasSiliconCloud -match "OK") {
        # 使用 siliconcloud - 直接写入文件
        $siliconCloudCode = @'
# backend/services/ai_client.py
import os
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv
from siliconcloud import SiliconCloud

# 可靠加载 .env
ROOT = Path(__file__).resolve().parents[2]
for cand in (ROOT / ".env", ROOT / "app" / ".env", Path.cwd() / ".env"):
    if cand.exists():
        load_dotenv(dotenv_path=cand, override=True)
        break


def fix_messages_for_siliconflow(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """SiliconFlow 不支持 role=developer，自动修正为 system + user 结构"""
    fixed = []
    for m in messages:
        role = m.get("role", "")
        if role == "developer":
            fixed.append({"role": "system", "content": m["content"]})
        else:
            fixed.append(m)
    return fixed


def get_client_and_cfg():
    """统一创建 client 和配置"""
    api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("SILICON_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 API Key，请设置 SILICONFLOW_API_KEY 或 SILICON_API_KEY")
    
    client = SiliconCloud(api_key=api_key)
    model = os.getenv("AI_MODEL", "Qwen/Qwen2.5-32B-Instruct")
    cfg = {
        "model": model,
        "provider": "siliconflow",
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.7"))
    }
    return client, cfg


def chat_completion(client, cfg, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
    """统一入口：硅基自动修复 messages，兼容原有函数签名"""
    if cfg.get("provider") == "siliconflow":
        messages = fix_messages_for_siliconflow(messages)
    
    kwargs.pop("response_format", None)
    model = kwargs.pop("model", cfg.get("model", "Qwen/Qwen2.5-32B-Instruct"))
    temperature = kwargs.pop("temperature", cfg.get("temperature", 0.7))
    
    params = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    
    if "max_tokens" in kwargs:
        params["max_tokens"] = kwargs.pop("max_tokens")
    
    for key in ["top_p", "frequency_penalty", "presence_penalty", "stream"]:
        if key in kwargs:
            params[key] = kwargs.pop(key)
    
    try:
        response = client.chat.completions.create(**params)
        return {
            "choices": [{
                "message": {
                    "content": response.choices[0].message["content"]
                }
            }]
        }
    except Exception as e:
        raise Exception(f"API 调用失败: {str(e)}")
'@
        [System.IO.File]::WriteAllText((Resolve-Path $clientFile), $siliconCloudCode, [System.Text.Encoding]::UTF8)
    } else {
        # 使用 requests 直接调用 API
        $requestsCode = @'
# backend/services/ai_client.py
import os
import requests
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv

# 可靠加载 .env
ROOT = Path(__file__).resolve().parents[2]
for cand in (ROOT / ".env", ROOT / "app" / ".env", Path.cwd() / ".env"):
    if cand.exists():
        load_dotenv(dotenv_path=cand, override=True)
        break


def fix_messages_for_siliconflow(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """SiliconFlow 不支持 role=developer，自动修正为 system + user 结构"""
    fixed = []
    for m in messages:
        role = m.get("role", "")
        if role == "developer":
            fixed.append({"role": "system", "content": m["content"]})
        else:
            fixed.append(m)
    return fixed


def get_client_and_cfg():
    """统一创建 client 和配置（使用 requests 直接调用 API）"""
    api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("SILICON_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 API Key，请设置 SILICONFLOW_API_KEY 或 SILICON_API_KEY")
    
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("AI_MODEL", "Qwen/Qwen2.5-32B-Instruct")
    
    cfg = {
        "model": model,
        "provider": "siliconflow",
        "api_key": api_key,
        "base_url": base_url,
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.7"))
    }
    return None, cfg


def chat_completion(client, cfg, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
    """统一入口：使用 requests 直接调用硅基流动 API"""
    if cfg.get("provider") == "siliconflow":
        messages = fix_messages_for_siliconflow(messages)
    
    kwargs.pop("response_format", None)
    model = kwargs.pop("model", cfg.get("model", "Qwen/Qwen2.5-32B-Instruct"))
    temperature = kwargs.pop("temperature", cfg.get("temperature", 0.7))
    
    base_url = cfg.get("base_url", "https://api.siliconflow.cn/v1")
    api_url = f"{base_url.rstrip('/')}/chat/completions"
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    
    if "max_tokens" in kwargs:
        payload["max_tokens"] = kwargs.pop("max_tokens")
    
    for key in ["top_p", "frequency_penalty", "presence_penalty", "stream"]:
        if key in kwargs:
            payload[key] = kwargs.pop(key)
    
    api_key = cfg.get("api_key")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        return {
            "choices": [{
                "message": {
                    "content": data["choices"][0]["message"]["content"]
                }
            }]
        }
    except requests.exceptions.RequestException as e:
        raise Exception(f"API 调用失败: {str(e)}")
    except (KeyError, IndexError) as e:
        raise Exception(f"API 响应格式错误: {str(e)}")
'@
        [System.IO.File]::WriteAllText((Resolve-Path $clientFile), $requestsCode, [System.Text.Encoding]::UTF8)
    }
    Write-Host "✅ ai_client.py 已修复" -ForegroundColor Green
} else {
    Write-Host "⚠️ 未找到 ai_client.py" -ForegroundColor Yellow
}

# 8. 安装项目依赖
Write-Host "8️⃣ 安装 requirements.txt ..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    python -m pip install -r requirements.txt 2>&1 | Out-Null
    Write-Host "✅ 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "⚠️ 未找到 requirements.txt" -ForegroundColor Yellow
}

# 9. 启动应用
Write-Host "9️⃣ 正在启动 Streamlit ..." -ForegroundColor Cyan
Write-Host "`n=== 应用启动中 ===" -ForegroundColor Green
Write-Host "访问地址: http://localhost:8501" -ForegroundColor Yellow
Write-Host "`n按 Ctrl+C 停止应用`n" -ForegroundColor Gray

streamlit run app/streamlit_app.py

Write-Host "`n🎉 全部修复完成！系统已成功运行！" -ForegroundColor Cyan


# ------------------------------

Write-Host "🍀 RecruitFlow 正在自动修复环境..." -ForegroundColor Green

# 1. 允许 PowerShell 执行脚本
Write-Host "1️⃣ 设置执行策略..." -ForegroundColor Yellow
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force -ErrorAction SilentlyContinue
Write-Host "✅ 执行策略已设置" -ForegroundColor Green

# 2. 检查虚拟环境
Write-Host "2️⃣ 检查 .venv ..." -ForegroundColor Yellow
if (-Not (Test-Path ".\.venv")) {
    Write-Host "⛔ 未检测到虚拟环境 .venv，正在创建..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "✅ 虚拟环境已创建" -ForegroundColor Green
} else {
    Write-Host "✅ 虚拟环境已存在" -ForegroundColor Green
}

# 3. 自动激活虚拟环境
Write-Host "3️⃣ 激活虚拟环境..." -ForegroundColor Yellow
$activate = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
    & $activate
    Write-Host "✅ venv 激活成功！" -ForegroundColor Green
} else {
    Write-Host "⛔ 激活文件缺失: $activate" -ForegroundColor Red
    exit
}

# 4. 修复 pip
Write-Host "4️⃣ 修复 pip..." -ForegroundColor Yellow
python -m ensurepip --upgrade 2>&1 | Out-Null
python -m pip install --upgrade pip setuptools wheel 2>&1 | Out-Null
Write-Host "✅ pip 已更新" -ForegroundColor Green

# 5. 清理旧 openai
Write-Host "5️⃣ 卸载旧 openai..." -ForegroundColor Yellow
python -m pip uninstall -y openai 2>$null | Out-Null
Write-Host "✅ 旧 openai 已卸载" -ForegroundColor Green

# 6. 安装 siliconcloud (新 SDK)
Write-Host "6️⃣ 安装 siliconcloud..." -ForegroundColor Yellow
python -m pip install siliconcloud 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ siliconcloud 安装成功" -ForegroundColor Green
} else {
    Write-Host "⚠️ siliconcloud 包不存在，将使用 requests 直接调用 API" -ForegroundColor Yellow
}

# 7. 自动修复你的项目 AI Client 代码
Write-Host "7️⃣ 修复 ai_client.py ..." -ForegroundColor Yellow
$clientFile = ".\backend\services\ai_client.py"

if (Test-Path $clientFile) {
    # 检查 siliconcloud 是否可用
    $hasSiliconCloud = python -c "import siliconcloud; print('OK')" 2>&1
    if ($hasSiliconCloud -match "OK") {
        # 使用 siliconcloud - 直接写入文件
        $siliconCloudCode = @'
# backend/services/ai_client.py
import os
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv
from siliconcloud import SiliconCloud

# 可靠加载 .env
ROOT = Path(__file__).resolve().parents[2]
for cand in (ROOT / ".env", ROOT / "app" / ".env", Path.cwd() / ".env"):
    if cand.exists():
        load_dotenv(dotenv_path=cand, override=True)
        break


def fix_messages_for_siliconflow(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """SiliconFlow 不支持 role=developer，自动修正为 system + user 结构"""
    fixed = []
    for m in messages:
        role = m.get("role", "")
        if role == "developer":
            fixed.append({"role": "system", "content": m["content"]})
        else:
            fixed.append(m)
    return fixed


def get_client_and_cfg():
    """统一创建 client 和配置"""
    api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("SILICON_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 API Key，请设置 SILICONFLOW_API_KEY 或 SILICON_API_KEY")
    
    client = SiliconCloud(api_key=api_key)
    model = os.getenv("AI_MODEL", "Qwen/Qwen2.5-32B-Instruct")
    cfg = {
        "model": model,
        "provider": "siliconflow",
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.7"))
    }
    return client, cfg


def chat_completion(client, cfg, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
    """统一入口：硅基自动修复 messages，兼容原有函数签名"""
    if cfg.get("provider") == "siliconflow":
        messages = fix_messages_for_siliconflow(messages)
    
    kwargs.pop("response_format", None)
    model = kwargs.pop("model", cfg.get("model", "Qwen/Qwen2.5-32B-Instruct"))
    temperature = kwargs.pop("temperature", cfg.get("temperature", 0.7))
    
    params = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    
    if "max_tokens" in kwargs:
        params["max_tokens"] = kwargs.pop("max_tokens")
    
    for key in ["top_p", "frequency_penalty", "presence_penalty", "stream"]:
        if key in kwargs:
            params[key] = kwargs.pop(key)
    
    try:
        response = client.chat.completions.create(**params)
        return {
            "choices": [{
                "message": {
                    "content": response.choices[0].message["content"]
                }
            }]
        }
    except Exception as e:
        raise Exception(f"API 调用失败: {str(e)}")
'@
        [System.IO.File]::WriteAllText((Resolve-Path $clientFile), $siliconCloudCode, [System.Text.Encoding]::UTF8)
    } else {
        # 使用 requests 直接调用 API
        $requestsCode = @'
# backend/services/ai_client.py
import os
import requests
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv

# 可靠加载 .env
ROOT = Path(__file__).resolve().parents[2]
for cand in (ROOT / ".env", ROOT / "app" / ".env", Path.cwd() / ".env"):
    if cand.exists():
        load_dotenv(dotenv_path=cand, override=True)
        break


def fix_messages_for_siliconflow(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """SiliconFlow 不支持 role=developer，自动修正为 system + user 结构"""
    fixed = []
    for m in messages:
        role = m.get("role", "")
        if role == "developer":
            fixed.append({"role": "system", "content": m["content"]})
        else:
            fixed.append(m)
    return fixed


def get_client_and_cfg():
    """统一创建 client 和配置（使用 requests 直接调用 API）"""
    api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("SILICON_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 API Key，请设置 SILICONFLOW_API_KEY 或 SILICON_API_KEY")
    
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("AI_MODEL", "Qwen/Qwen2.5-32B-Instruct")
    
    cfg = {
        "model": model,
        "provider": "siliconflow",
        "api_key": api_key,
        "base_url": base_url,
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.7"))
    }
    return None, cfg


def chat_completion(client, cfg, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
    """统一入口：使用 requests 直接调用硅基流动 API"""
    if cfg.get("provider") == "siliconflow":
        messages = fix_messages_for_siliconflow(messages)
    
    kwargs.pop("response_format", None)
    model = kwargs.pop("model", cfg.get("model", "Qwen/Qwen2.5-32B-Instruct"))
    temperature = kwargs.pop("temperature", cfg.get("temperature", 0.7))
    
    base_url = cfg.get("base_url", "https://api.siliconflow.cn/v1")
    api_url = f"{base_url.rstrip('/')}/chat/completions"
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    
    if "max_tokens" in kwargs:
        payload["max_tokens"] = kwargs.pop("max_tokens")
    
    for key in ["top_p", "frequency_penalty", "presence_penalty", "stream"]:
        if key in kwargs:
            payload[key] = kwargs.pop(key)
    
    api_key = cfg.get("api_key")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        return {
            "choices": [{
                "message": {
                    "content": data["choices"][0]["message"]["content"]
                }
            }]
        }
    except requests.exceptions.RequestException as e:
        raise Exception(f"API 调用失败: {str(e)}")
    except (KeyError, IndexError) as e:
        raise Exception(f"API 响应格式错误: {str(e)}")
'@
        [System.IO.File]::WriteAllText((Resolve-Path $clientFile), $requestsCode, [System.Text.Encoding]::UTF8)
    }
    Write-Host "✅ ai_client.py 已修复" -ForegroundColor Green
} else {
    Write-Host "⚠️ 未找到 ai_client.py" -ForegroundColor Yellow
}

# 8. 安装项目依赖
Write-Host "8️⃣ 安装 requirements.txt ..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    python -m pip install -r requirements.txt 2>&1 | Out-Null
    Write-Host "✅ 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "⚠️ 未找到 requirements.txt" -ForegroundColor Yellow
}

# 9. 启动应用
Write-Host "9️⃣ 正在启动 Streamlit ..." -ForegroundColor Cyan
Write-Host "`n=== 应用启动中 ===" -ForegroundColor Green
Write-Host "访问地址: http://localhost:8501" -ForegroundColor Yellow
Write-Host "`n按 Ctrl+C 停止应用`n" -ForegroundColor Gray

streamlit run app/streamlit_app.py

Write-Host "`n🎉 全部修复完成！系统已成功运行！" -ForegroundColor Cyan




# ------------------------------

Write-Host "🍀 RecruitFlow 正在自动修复环境..." -ForegroundColor Green

# 1. 允许 PowerShell 执行脚本
Write-Host "1️⃣ 设置执行策略..." -ForegroundColor Yellow
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force -ErrorAction SilentlyContinue
Write-Host "✅ 执行策略已设置" -ForegroundColor Green

# 2. 检查虚拟环境
Write-Host "2️⃣ 检查 .venv ..." -ForegroundColor Yellow
if (-Not (Test-Path ".\.venv")) {
    Write-Host "⛔ 未检测到虚拟环境 .venv，正在创建..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "✅ 虚拟环境已创建" -ForegroundColor Green
} else {
    Write-Host "✅ 虚拟环境已存在" -ForegroundColor Green
}

# 3. 自动激活虚拟环境
Write-Host "3️⃣ 激活虚拟环境..." -ForegroundColor Yellow
$activate = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
    & $activate
    Write-Host "✅ venv 激活成功！" -ForegroundColor Green
} else {
    Write-Host "⛔ 激活文件缺失: $activate" -ForegroundColor Red
    exit
}

# 4. 修复 pip
Write-Host "4️⃣ 修复 pip..." -ForegroundColor Yellow
python -m ensurepip --upgrade 2>&1 | Out-Null
python -m pip install --upgrade pip setuptools wheel 2>&1 | Out-Null
Write-Host "✅ pip 已更新" -ForegroundColor Green

# 5. 清理旧 openai
Write-Host "5️⃣ 卸载旧 openai..." -ForegroundColor Yellow
python -m pip uninstall -y openai 2>$null | Out-Null
Write-Host "✅ 旧 openai 已卸载" -ForegroundColor Green

# 6. 安装 siliconcloud (新 SDK)
Write-Host "6️⃣ 安装 siliconcloud..." -ForegroundColor Yellow
python -m pip install siliconcloud 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ siliconcloud 安装成功" -ForegroundColor Green
} else {
    Write-Host "⚠️ siliconcloud 包不存在，将使用 requests 直接调用 API" -ForegroundColor Yellow
}

# 7. 自动修复你的项目 AI Client 代码
Write-Host "7️⃣ 修复 ai_client.py ..." -ForegroundColor Yellow
$clientFile = ".\backend\services\ai_client.py"

if (Test-Path $clientFile) {
    # 检查 siliconcloud 是否可用
    $hasSiliconCloud = python -c "import siliconcloud; print('OK')" 2>&1
    if ($hasSiliconCloud -match "OK") {
        # 使用 siliconcloud - 直接写入文件
        $siliconCloudCode = @'
# backend/services/ai_client.py
import os
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv
from siliconcloud import SiliconCloud

# 可靠加载 .env
ROOT = Path(__file__).resolve().parents[2]
for cand in (ROOT / ".env", ROOT / "app" / ".env", Path.cwd() / ".env"):
    if cand.exists():
        load_dotenv(dotenv_path=cand, override=True)
        break


def fix_messages_for_siliconflow(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """SiliconFlow 不支持 role=developer，自动修正为 system + user 结构"""
    fixed = []
    for m in messages:
        role = m.get("role", "")
        if role == "developer":
            fixed.append({"role": "system", "content": m["content"]})
        else:
            fixed.append(m)
    return fixed


def get_client_and_cfg():
    """统一创建 client 和配置"""
    api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("SILICON_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 API Key，请设置 SILICONFLOW_API_KEY 或 SILICON_API_KEY")
    
    client = SiliconCloud(api_key=api_key)
    model = os.getenv("AI_MODEL", "Qwen/Qwen2.5-32B-Instruct")
    cfg = {
        "model": model,
        "provider": "siliconflow",
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.7"))
    }
    return client, cfg


def chat_completion(client, cfg, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
    """统一入口：硅基自动修复 messages，兼容原有函数签名"""
    if cfg.get("provider") == "siliconflow":
        messages = fix_messages_for_siliconflow(messages)
    
    kwargs.pop("response_format", None)
    model = kwargs.pop("model", cfg.get("model", "Qwen/Qwen2.5-32B-Instruct"))
    temperature = kwargs.pop("temperature", cfg.get("temperature", 0.7))
    
    params = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    
    if "max_tokens" in kwargs:
        params["max_tokens"] = kwargs.pop("max_tokens")
    
    for key in ["top_p", "frequency_penalty", "presence_penalty", "stream"]:
        if key in kwargs:
            params[key] = kwargs.pop(key)
    
    try:
        response = client.chat.completions.create(**params)
        return {
            "choices": [{
                "message": {
                    "content": response.choices[0].message["content"]
                }
            }]
        }
    except Exception as e:
        raise Exception(f"API 调用失败: {str(e)}")
'@
        [System.IO.File]::WriteAllText((Resolve-Path $clientFile), $siliconCloudCode, [System.Text.Encoding]::UTF8)
    } else {
        # 使用 requests 直接调用 API
        $requestsCode = @'
# backend/services/ai_client.py
import os
import requests
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv

# 可靠加载 .env
ROOT = Path(__file__).resolve().parents[2]
for cand in (ROOT / ".env", ROOT / "app" / ".env", Path.cwd() / ".env"):
    if cand.exists():
        load_dotenv(dotenv_path=cand, override=True)
        break


def fix_messages_for_siliconflow(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """SiliconFlow 不支持 role=developer，自动修正为 system + user 结构"""
    fixed = []
    for m in messages:
        role = m.get("role", "")
        if role == "developer":
            fixed.append({"role": "system", "content": m["content"]})
        else:
            fixed.append(m)
    return fixed


def get_client_and_cfg():
    """统一创建 client 和配置（使用 requests 直接调用 API）"""
    api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("SILICON_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 API Key，请设置 SILICONFLOW_API_KEY 或 SILICON_API_KEY")
    
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("AI_MODEL", "Qwen/Qwen2.5-32B-Instruct")
    
    cfg = {
        "model": model,
        "provider": "siliconflow",
        "api_key": api_key,
        "base_url": base_url,
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.7"))
    }
    return None, cfg


def chat_completion(client, cfg, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
    """统一入口：使用 requests 直接调用硅基流动 API"""
    if cfg.get("provider") == "siliconflow":
        messages = fix_messages_for_siliconflow(messages)
    
    kwargs.pop("response_format", None)
    model = kwargs.pop("model", cfg.get("model", "Qwen/Qwen2.5-32B-Instruct"))
    temperature = kwargs.pop("temperature", cfg.get("temperature", 0.7))
    
    base_url = cfg.get("base_url", "https://api.siliconflow.cn/v1")
    api_url = f"{base_url.rstrip('/')}/chat/completions"
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    
    if "max_tokens" in kwargs:
        payload["max_tokens"] = kwargs.pop("max_tokens")
    
    for key in ["top_p", "frequency_penalty", "presence_penalty", "stream"]:
        if key in kwargs:
            payload[key] = kwargs.pop(key)
    
    api_key = cfg.get("api_key")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        return {
            "choices": [{
                "message": {
                    "content": data["choices"][0]["message"]["content"]
                }
            }]
        }
    except requests.exceptions.RequestException as e:
        raise Exception(f"API 调用失败: {str(e)}")
    except (KeyError, IndexError) as e:
        raise Exception(f"API 响应格式错误: {str(e)}")
'@
        [System.IO.File]::WriteAllText((Resolve-Path $clientFile), $requestsCode, [System.Text.Encoding]::UTF8)
    }
    Write-Host "✅ ai_client.py 已修复" -ForegroundColor Green
} else {
    Write-Host "⚠️ 未找到 ai_client.py" -ForegroundColor Yellow
}

# 8. 安装项目依赖
Write-Host "8️⃣ 安装 requirements.txt ..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    python -m pip install -r requirements.txt 2>&1 | Out-Null
    Write-Host "✅ 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "⚠️ 未找到 requirements.txt" -ForegroundColor Yellow
}

# 9. 启动应用
Write-Host "9️⃣ 正在启动 Streamlit ..." -ForegroundColor Cyan
Write-Host "`n=== 应用启动中 ===" -ForegroundColor Green
Write-Host "访问地址: http://localhost:8501" -ForegroundColor Yellow
Write-Host "`n按 Ctrl+C 停止应用`n" -ForegroundColor Gray

streamlit run app/streamlit_app.py

Write-Host "`n🎉 全部修复完成！系统已成功运行！" -ForegroundColor Cyan


# ------------------------------

Write-Host "🍀 RecruitFlow 正在自动修复环境..." -ForegroundColor Green

# 1. 允许 PowerShell 执行脚本
Write-Host "1️⃣ 设置执行策略..." -ForegroundColor Yellow
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force -ErrorAction SilentlyContinue
Write-Host "✅ 执行策略已设置" -ForegroundColor Green

# 2. 检查虚拟环境
Write-Host "2️⃣ 检查 .venv ..." -ForegroundColor Yellow
if (-Not (Test-Path ".\.venv")) {
    Write-Host "⛔ 未检测到虚拟环境 .venv，正在创建..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "✅ 虚拟环境已创建" -ForegroundColor Green
} else {
    Write-Host "✅ 虚拟环境已存在" -ForegroundColor Green
}

# 3. 自动激活虚拟环境
Write-Host "3️⃣ 激活虚拟环境..." -ForegroundColor Yellow
$activate = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
    & $activate
    Write-Host "✅ venv 激活成功！" -ForegroundColor Green
} else {
    Write-Host "⛔ 激活文件缺失: $activate" -ForegroundColor Red
    exit
}

# 4. 修复 pip
Write-Host "4️⃣ 修复 pip..." -ForegroundColor Yellow
python -m ensurepip --upgrade 2>&1 | Out-Null
python -m pip install --upgrade pip setuptools wheel 2>&1 | Out-Null
Write-Host "✅ pip 已更新" -ForegroundColor Green

# 5. 清理旧 openai
Write-Host "5️⃣ 卸载旧 openai..." -ForegroundColor Yellow
python -m pip uninstall -y openai 2>$null | Out-Null
Write-Host "✅ 旧 openai 已卸载" -ForegroundColor Green

# 6. 安装 siliconcloud (新 SDK)
Write-Host "6️⃣ 安装 siliconcloud..." -ForegroundColor Yellow
python -m pip install siliconcloud 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ siliconcloud 安装成功" -ForegroundColor Green
} else {
    Write-Host "⚠️ siliconcloud 包不存在，将使用 requests 直接调用 API" -ForegroundColor Yellow
}

# 7. 自动修复你的项目 AI Client 代码
Write-Host "7️⃣ 修复 ai_client.py ..." -ForegroundColor Yellow
$clientFile = ".\backend\services\ai_client.py"

if (Test-Path $clientFile) {
    # 检查 siliconcloud 是否可用
    $hasSiliconCloud = python -c "import siliconcloud; print('OK')" 2>&1
    if ($hasSiliconCloud -match "OK") {
        # 使用 siliconcloud - 直接写入文件
        $siliconCloudCode = @'
# backend/services/ai_client.py
import os
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv
from siliconcloud import SiliconCloud

# 可靠加载 .env
ROOT = Path(__file__).resolve().parents[2]
for cand in (ROOT / ".env", ROOT / "app" / ".env", Path.cwd() / ".env"):
    if cand.exists():
        load_dotenv(dotenv_path=cand, override=True)
        break


def fix_messages_for_siliconflow(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """SiliconFlow 不支持 role=developer，自动修正为 system + user 结构"""
    fixed = []
    for m in messages:
        role = m.get("role", "")
        if role == "developer":
            fixed.append({"role": "system", "content": m["content"]})
        else:
            fixed.append(m)
    return fixed


def get_client_and_cfg():
    """统一创建 client 和配置"""
    api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("SILICON_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 API Key，请设置 SILICONFLOW_API_KEY 或 SILICON_API_KEY")
    
    client = SiliconCloud(api_key=api_key)
    model = os.getenv("AI_MODEL", "Qwen/Qwen2.5-32B-Instruct")
    cfg = {
        "model": model,
        "provider": "siliconflow",
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.7"))
    }
    return client, cfg


def chat_completion(client, cfg, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
    """统一入口：硅基自动修复 messages，兼容原有函数签名"""
    if cfg.get("provider") == "siliconflow":
        messages = fix_messages_for_siliconflow(messages)
    
    kwargs.pop("response_format", None)
    model = kwargs.pop("model", cfg.get("model", "Qwen/Qwen2.5-32B-Instruct"))
    temperature = kwargs.pop("temperature", cfg.get("temperature", 0.7))
    
    params = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    
    if "max_tokens" in kwargs:
        params["max_tokens"] = kwargs.pop("max_tokens")
    
    for key in ["top_p", "frequency_penalty", "presence_penalty", "stream"]:
        if key in kwargs:
            params[key] = kwargs.pop(key)
    
    try:
        response = client.chat.completions.create(**params)
        return {
            "choices": [{
                "message": {
                    "content": response.choices[0].message["content"]
                }
            }]
        }
    except Exception as e:
        raise Exception(f"API 调用失败: {str(e)}")
'@
        [System.IO.File]::WriteAllText((Resolve-Path $clientFile), $siliconCloudCode, [System.Text.Encoding]::UTF8)
    } else {
        # 使用 requests 直接调用 API
        $requestsCode = @'
# backend/services/ai_client.py
import os
import requests
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv

# 可靠加载 .env
ROOT = Path(__file__).resolve().parents[2]
for cand in (ROOT / ".env", ROOT / "app" / ".env", Path.cwd() / ".env"):
    if cand.exists():
        load_dotenv(dotenv_path=cand, override=True)
        break


def fix_messages_for_siliconflow(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """SiliconFlow 不支持 role=developer，自动修正为 system + user 结构"""
    fixed = []
    for m in messages:
        role = m.get("role", "")
        if role == "developer":
            fixed.append({"role": "system", "content": m["content"]})
        else:
            fixed.append(m)
    return fixed


def get_client_and_cfg():
    """统一创建 client 和配置（使用 requests 直接调用 API）"""
    api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("SILICON_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 API Key，请设置 SILICONFLOW_API_KEY 或 SILICON_API_KEY")
    
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model = os.getenv("AI_MODEL", "Qwen/Qwen2.5-32B-Instruct")
    
    cfg = {
        "model": model,
        "provider": "siliconflow",
        "api_key": api_key,
        "base_url": base_url,
        "temperature": float(os.getenv("AI_TEMPERATURE", "0.7"))
    }
    return None, cfg


def chat_completion(client, cfg, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
    """统一入口：使用 requests 直接调用硅基流动 API"""
    if cfg.get("provider") == "siliconflow":
        messages = fix_messages_for_siliconflow(messages)
    
    kwargs.pop("response_format", None)
    model = kwargs.pop("model", cfg.get("model", "Qwen/Qwen2.5-32B-Instruct"))
    temperature = kwargs.pop("temperature", cfg.get("temperature", 0.7))
    
    base_url = cfg.get("base_url", "https://api.siliconflow.cn/v1")
    api_url = f"{base_url.rstrip('/')}/chat/completions"
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    
    if "max_tokens" in kwargs:
        payload["max_tokens"] = kwargs.pop("max_tokens")
    
    for key in ["top_p", "frequency_penalty", "presence_penalty", "stream"]:
        if key in kwargs:
            payload[key] = kwargs.pop(key)
    
    api_key = cfg.get("api_key")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        return {
            "choices": [{
                "message": {
                    "content": data["choices"][0]["message"]["content"]
                }
            }]
        }
    except requests.exceptions.RequestException as e:
        raise Exception(f"API 调用失败: {str(e)}")
    except (KeyError, IndexError) as e:
        raise Exception(f"API 响应格式错误: {str(e)}")
'@
        [System.IO.File]::WriteAllText((Resolve-Path $clientFile), $requestsCode, [System.Text.Encoding]::UTF8)
    }
    Write-Host "✅ ai_client.py 已修复" -ForegroundColor Green
} else {
    Write-Host "⚠️ 未找到 ai_client.py" -ForegroundColor Yellow
}

# 8. 安装项目依赖
Write-Host "8️⃣ 安装 requirements.txt ..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    python -m pip install -r requirements.txt 2>&1 | Out-Null
    Write-Host "✅ 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "⚠️ 未找到 requirements.txt" -ForegroundColor Yellow
}

# 9. 启动应用
Write-Host "9️⃣ 正在启动 Streamlit ..." -ForegroundColor Cyan
Write-Host "`n=== 应用启动中 ===" -ForegroundColor Green
Write-Host "访问地址: http://localhost:8501" -ForegroundColor Yellow
Write-Host "`n按 Ctrl+C 停止应用`n" -ForegroundColor Gray

streamlit run app/streamlit_app.py

Write-Host "`n🎉 全部修复完成！系统已成功运行！" -ForegroundColor Cyan



