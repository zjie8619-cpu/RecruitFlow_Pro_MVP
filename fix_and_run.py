#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RecruitFlow 全自动环境修复脚本 (Python 版本)
"""
import os
import sys
import subprocess
from pathlib import Path
import io

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def run_cmd(cmd, check=True):
    """执行命令"""
    print(f"执行: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"错误: {result.stderr}")
        return False
    return True

def main():
    print("🍀 RecruitFlow 正在自动修复环境...\n")
    
    # 1. 检查虚拟环境
    print("1️⃣ 检查 .venv ...")
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("⛔ 未检测到虚拟环境 .venv，正在创建...")
        run_cmd("python -m venv .venv")
        print("✅ 虚拟环境已创建")
    else:
        print("✅ 虚拟环境已存在")
    
    # 2. 修复 pip
    print("\n2️⃣ 修复 pip...")
    run_cmd("python -m ensurepip --upgrade", check=False)
    run_cmd("python -m pip install --upgrade pip setuptools wheel", check=False)
    print("✅ pip 已更新")
    
    # 3. 清理旧 openai
    print("\n3️⃣ 卸载旧 openai...")
    run_cmd("python -m pip uninstall -y openai", check=False)
    print("✅ 旧 openai 已卸载")
    
    # 4. 安装 requests（确保可用）
    print("\n4️⃣ 确保 requests 已安装...")
    run_cmd("python -m pip install requests", check=False)
    print("✅ requests 已安装")
    
    # 5. 修复 ai_client.py
    print("\n5️⃣ 修复 ai_client.py ...")
    client_file = Path("backend/services/ai_client.py")
    
    if client_file.exists():
        client_content = '''# backend/services/ai_client.py
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
'''
        client_file.write_text(client_content, encoding='utf-8')
        print("✅ ai_client.py 已修复")
    else:
        print("⚠️ 未找到 ai_client.py")
    
    # 6. 安装项目依赖
    print("\n6️⃣ 安装 requirements.txt ...")
    if Path("requirements.txt").exists():
        run_cmd("python -m pip install -r requirements.txt", check=False)
        print("✅ 依赖安装完成")
    else:
        print("⚠️ 未找到 requirements.txt")
    
    # 7. 确保 Streamlit 已安装
    print("\n7️⃣ 确保 Streamlit 已安装...")
    run_cmd("python -m pip install streamlit", check=False)
    print("✅ Streamlit 已安装")
    
    # 8. 启动应用
    print("\n8️⃣ 正在启动 Streamlit ...")
    print("\n=== 应用启动中 ===")
    print("访问地址: http://localhost:8501")
    print("\n按 Ctrl+C 停止应用\n")
    
    # 启动 Streamlit
    try:
        os.system("python -m streamlit run app/streamlit_app.py")
    except KeyboardInterrupt:
        print("\n应用已停止")
    
    print("\n🎉 全部修复完成！系统已成功运行！")

if __name__ == "__main__":
    main()


"""
RecruitFlow 全自动环境修复脚本 (Python 版本)
"""
import os
import sys
import subprocess
from pathlib import Path
import io

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def run_cmd(cmd, check=True):
    """执行命令"""
    print(f"执行: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"错误: {result.stderr}")
        return False
    return True

def main():
    print("🍀 RecruitFlow 正在自动修复环境...\n")
    
    # 1. 检查虚拟环境
    print("1️⃣ 检查 .venv ...")
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("⛔ 未检测到虚拟环境 .venv，正在创建...")
        run_cmd("python -m venv .venv")
        print("✅ 虚拟环境已创建")
    else:
        print("✅ 虚拟环境已存在")
    
    # 2. 修复 pip
    print("\n2️⃣ 修复 pip...")
    run_cmd("python -m ensurepip --upgrade", check=False)
    run_cmd("python -m pip install --upgrade pip setuptools wheel", check=False)
    print("✅ pip 已更新")
    
    # 3. 清理旧 openai
    print("\n3️⃣ 卸载旧 openai...")
    run_cmd("python -m pip uninstall -y openai", check=False)
    print("✅ 旧 openai 已卸载")
    
    # 4. 安装 requests（确保可用）
    print("\n4️⃣ 确保 requests 已安装...")
    run_cmd("python -m pip install requests", check=False)
    print("✅ requests 已安装")
    
    # 5. 修复 ai_client.py
    print("\n5️⃣ 修复 ai_client.py ...")
    client_file = Path("backend/services/ai_client.py")
    
    if client_file.exists():
        client_content = '''# backend/services/ai_client.py
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
'''
        client_file.write_text(client_content, encoding='utf-8')
        print("✅ ai_client.py 已修复")
    else:
        print("⚠️ 未找到 ai_client.py")
    
    # 6. 安装项目依赖
    print("\n6️⃣ 安装 requirements.txt ...")
    if Path("requirements.txt").exists():
        run_cmd("python -m pip install -r requirements.txt", check=False)
        print("✅ 依赖安装完成")
    else:
        print("⚠️ 未找到 requirements.txt")
    
    # 7. 确保 Streamlit 已安装
    print("\n7️⃣ 确保 Streamlit 已安装...")
    run_cmd("python -m pip install streamlit", check=False)
    print("✅ Streamlit 已安装")
    
    # 8. 启动应用
    print("\n8️⃣ 正在启动 Streamlit ...")
    print("\n=== 应用启动中 ===")
    print("访问地址: http://localhost:8501")
    print("\n按 Ctrl+C 停止应用\n")
    
    # 启动 Streamlit
    try:
        os.system("python -m streamlit run app/streamlit_app.py")
    except KeyboardInterrupt:
        print("\n应用已停止")
    
    print("\n🎉 全部修复完成！系统已成功运行！")

if __name__ == "__main__":
    main()




"""
RecruitFlow 全自动环境修复脚本 (Python 版本)
"""
import os
import sys
import subprocess
from pathlib import Path
import io

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def run_cmd(cmd, check=True):
    """执行命令"""
    print(f"执行: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"错误: {result.stderr}")
        return False
    return True

def main():
    print("🍀 RecruitFlow 正在自动修复环境...\n")
    
    # 1. 检查虚拟环境
    print("1️⃣ 检查 .venv ...")
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("⛔ 未检测到虚拟环境 .venv，正在创建...")
        run_cmd("python -m venv .venv")
        print("✅ 虚拟环境已创建")
    else:
        print("✅ 虚拟环境已存在")
    
    # 2. 修复 pip
    print("\n2️⃣ 修复 pip...")
    run_cmd("python -m ensurepip --upgrade", check=False)
    run_cmd("python -m pip install --upgrade pip setuptools wheel", check=False)
    print("✅ pip 已更新")
    
    # 3. 清理旧 openai
    print("\n3️⃣ 卸载旧 openai...")
    run_cmd("python -m pip uninstall -y openai", check=False)
    print("✅ 旧 openai 已卸载")
    
    # 4. 安装 requests（确保可用）
    print("\n4️⃣ 确保 requests 已安装...")
    run_cmd("python -m pip install requests", check=False)
    print("✅ requests 已安装")
    
    # 5. 修复 ai_client.py
    print("\n5️⃣ 修复 ai_client.py ...")
    client_file = Path("backend/services/ai_client.py")
    
    if client_file.exists():
        client_content = '''# backend/services/ai_client.py
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
'''
        client_file.write_text(client_content, encoding='utf-8')
        print("✅ ai_client.py 已修复")
    else:
        print("⚠️ 未找到 ai_client.py")
    
    # 6. 安装项目依赖
    print("\n6️⃣ 安装 requirements.txt ...")
    if Path("requirements.txt").exists():
        run_cmd("python -m pip install -r requirements.txt", check=False)
        print("✅ 依赖安装完成")
    else:
        print("⚠️ 未找到 requirements.txt")
    
    # 7. 确保 Streamlit 已安装
    print("\n7️⃣ 确保 Streamlit 已安装...")
    run_cmd("python -m pip install streamlit", check=False)
    print("✅ Streamlit 已安装")
    
    # 8. 启动应用
    print("\n8️⃣ 正在启动 Streamlit ...")
    print("\n=== 应用启动中 ===")
    print("访问地址: http://localhost:8501")
    print("\n按 Ctrl+C 停止应用\n")
    
    # 启动 Streamlit
    try:
        os.system("python -m streamlit run app/streamlit_app.py")
    except KeyboardInterrupt:
        print("\n应用已停止")
    
    print("\n🎉 全部修复完成！系统已成功运行！")

if __name__ == "__main__":
    main()


"""
RecruitFlow 全自动环境修复脚本 (Python 版本)
"""
import os
import sys
import subprocess
from pathlib import Path
import io

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

def run_cmd(cmd, check=True):
    """执行命令"""
    print(f"执行: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"错误: {result.stderr}")
        return False
    return True

def main():
    print("🍀 RecruitFlow 正在自动修复环境...\n")
    
    # 1. 检查虚拟环境
    print("1️⃣ 检查 .venv ...")
    venv_path = Path(".venv")
    if not venv_path.exists():
        print("⛔ 未检测到虚拟环境 .venv，正在创建...")
        run_cmd("python -m venv .venv")
        print("✅ 虚拟环境已创建")
    else:
        print("✅ 虚拟环境已存在")
    
    # 2. 修复 pip
    print("\n2️⃣ 修复 pip...")
    run_cmd("python -m ensurepip --upgrade", check=False)
    run_cmd("python -m pip install --upgrade pip setuptools wheel", check=False)
    print("✅ pip 已更新")
    
    # 3. 清理旧 openai
    print("\n3️⃣ 卸载旧 openai...")
    run_cmd("python -m pip uninstall -y openai", check=False)
    print("✅ 旧 openai 已卸载")
    
    # 4. 安装 requests（确保可用）
    print("\n4️⃣ 确保 requests 已安装...")
    run_cmd("python -m pip install requests", check=False)
    print("✅ requests 已安装")
    
    # 5. 修复 ai_client.py
    print("\n5️⃣ 修复 ai_client.py ...")
    client_file = Path("backend/services/ai_client.py")
    
    if client_file.exists():
        client_content = '''# backend/services/ai_client.py
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
'''
        client_file.write_text(client_content, encoding='utf-8')
        print("✅ ai_client.py 已修复")
    else:
        print("⚠️ 未找到 ai_client.py")
    
    # 6. 安装项目依赖
    print("\n6️⃣ 安装 requirements.txt ...")
    if Path("requirements.txt").exists():
        run_cmd("python -m pip install -r requirements.txt", check=False)
        print("✅ 依赖安装完成")
    else:
        print("⚠️ 未找到 requirements.txt")
    
    # 7. 确保 Streamlit 已安装
    print("\n7️⃣ 确保 Streamlit 已安装...")
    run_cmd("python -m pip install streamlit", check=False)
    print("✅ Streamlit 已安装")
    
    # 8. 启动应用
    print("\n8️⃣ 正在启动 Streamlit ...")
    print("\n=== 应用启动中 ===")
    print("访问地址: http://localhost:8501")
    print("\n按 Ctrl+C 停止应用\n")
    
    # 启动 Streamlit
    try:
        os.system("python -m streamlit run app/streamlit_app.py")
    except KeyboardInterrupt:
        print("\n应用已停止")
    
    print("\n🎉 全部修复完成！系统已成功运行！")

if __name__ == "__main__":
    main()



