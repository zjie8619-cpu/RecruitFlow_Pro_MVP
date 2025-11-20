# backend/services/ai_client.py
import os
from pathlib import Path
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv
from openai import OpenAI

# 可靠加载 .env
ROOT = Path(__file__).resolve().parents[2]
for cand in (ROOT / ".env", ROOT / "app" / ".env", Path.cwd() / ".env"):
    if cand.exists():
        load_dotenv(dotenv_path=cand, override=True)
        break


@dataclass
class AIConfig:
    provider: str = None
    api_key: str = None
    base_url: str = None
    model: str = None
    temperature: float = None

    def __post_init__(self):
        """自动识别硅基 / OpenAI"""
        if self.provider is None and self.api_key is None:
            if os.getenv("SILICONFLOW_API_KEY"):
                self.provider = "siliconflow"
                self.api_key = os.getenv("SILICONFLOW_API_KEY")
                self.base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
                self.model = os.getenv("AI_MODEL", "Qwen2.5-32B-Instruct")
                self.temperature = float(os.getenv("AI_TEMPERATURE", "0.7"))
            elif os.getenv("OPENAI_API_KEY"):
                self.provider = "openai"
                self.api_key = os.getenv("OPENAI_API_KEY")
                self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
                self.model = os.getenv("AI_MODEL", "gpt-4o-mini")
                self.temperature = float(os.getenv("AI_TEMPERATURE", "0.7"))
            else:
                raise RuntimeError("未配置 API Key")


def fix_messages_for_siliconflow(messages):
    """
    SiliconFlow 不支持 role=developer，不支持 response_format。
    自动修正为 system + user 结构。
    """
    fixed = []
    for m in messages:
        role = m.get("role", "")

        if role == "developer":
            # developer → system（最兼容）
            fixed.append({"role": "system", "content": m["content"]})
        else:
            fixed.append(m)

    return fixed


def get_client_and_cfg():
    """统一创建 client"""
    cfg = AIConfig()
    proxy = os.getenv("PROXY_URL") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")

    if proxy:
        http_client = httpx.Client(proxies=proxy, timeout=60.0)
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, http_client=http_client)
    else:
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

    return client, cfg


def chat_completion(client, cfg, messages, **kwargs):
    """
    🚀 统一入口：硅基自动修复 messages
    """
    if cfg.provider == "siliconflow":
        messages = fix_messages_for_siliconflow(messages)
        kwargs.pop("response_format", None)   # 删除不支持的字段

    return client.chat.completions.create(
        model=cfg.model,
        messages=messages,
        **kwargs
    )
