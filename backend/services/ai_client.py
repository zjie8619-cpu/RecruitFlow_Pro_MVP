# backend/services/ai_client.py
import os
from pathlib import Path
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv
from openai import OpenAI

# 1) 可靠加载 .env（优先根/.env → app/.env → 当前目录/.env）
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
        """支持无参初始化：自动从环境变量装填；若没配 Key，也返回占位。"""
        if self.provider is None and self.api_key is None:
            if os.getenv("SILICONFLOW_API_KEY"):
                self.provider = "siliconflow"
                self.api_key = os.getenv("SILICONFLOW_API_KEY")
                self.base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
                self.model = os.getenv("AI_MODEL", os.getenv("SILICONFLOW_MODEL", "gpt-4o-mini"))
                self.temperature = float(os.getenv("AI_TEMPERATURE", "0.7"))
            elif os.getenv("OPENAI_API_KEY"):
                self.provider = "openai"
                self.api_key = os.getenv("OPENAI_API_KEY")
                self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
                self.model = os.getenv("AI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4"))
                self.temperature = float(os.getenv("AI_TEMPERATURE", "0.7"))
            else:
                self.provider = ""
                self.api_key = ""
                self.base_url = ""
                self.model = os.getenv("AI_MODEL", "gpt-4o-mini")
                self.temperature = float(os.getenv("AI_TEMPERATURE", "0.7"))


def get_client_and_cfg():
    """用于真正发起请求：没有 Key 就抛错；有代理则用 httpx 客户端。"""

    cfg = AIConfig()
    if not cfg.api_key:
        raise RuntimeError("未检测到 API Key：请在项目根目录 `.env` 写入 SILICONFLOW_API_KEY 或 OPENAI_API_KEY（重启生效）。")

    proxy = os.getenv("PROXY_URL") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if proxy:
        http_client = httpx.Client(proxies=proxy, timeout=60.0)
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, http_client=http_client)
    else:
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

    return client, cfg
