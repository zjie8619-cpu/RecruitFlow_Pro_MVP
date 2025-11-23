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
    \"\"\"SiliconFlow 不支持 role=developer，自动修正为 system + user 结构\"\"\"
    fixed = []
    for m in messages:
        role = m.get("role", "")
        if role == "developer":
            fixed.append({"role": "system", "content": m["content"]})
        else:
            fixed.append(m)
    return fixed


def get_client_and_cfg():
    \"\"\"统一创建 client 和配置（使用 requests 直接调用 API）\"\"\"
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
    \"\"\"统一入口：使用 requests 直接调用硅基流动 API\"\"\"
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
