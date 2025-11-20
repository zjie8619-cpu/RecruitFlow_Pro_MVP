# backend/services/ai_client.py
import os
from pathlib import Path
from dataclasses import dataclass

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
                # raise RuntimeError("未配置 API Key")
                pass


def fix_messages_for_siliconflow(messages):
    """
#     SiliconFlow 不支持 role=developer,不支持 response_format.
#     自动修正为 system + user 结构.
    """
    fixed = []
    for m in messages:
        role = m.get("role", "")

        if role == "developer":
            # developer → system(最兼容)
            fixed.append({"role": "system", "content": m["content"]})
        else:
            fixed.append(m)

    return fixed


def get_client_and_cfg():
    """统一创建 client"""
    cfg = AIConfig()
    client = OpenAI(
        api_key=cfg.api_key,
        base_url=cfg.base_url
    )
    return client, cfg


def chat_completion(client, cfg, messages, **kwargs):
    """
    🚀 统一入口:硅基自动修复 messages
    使用新版本的 OpenAI SDK (>=1.0.0) 兼容格式
    """
    # 确保 client 是 OpenAI 实例，而不是 openai 模块
    if not hasattr(client, 'chat') or not hasattr(client.chat, 'completions'):
        # 如果传入的不是正确的 OpenAI 客户端，尝试重新创建
        if cfg.api_key and cfg.base_url:
            client = OpenAI(
                api_key=cfg.api_key,
                base_url=cfg.base_url
            )
        else:
            raise ValueError(
                "客户端对象无效。请确保使用 OpenAI() 实例，而不是 openai 模块。"
                "如果使用 get_client_and_cfg()，它会返回正确的客户端。"
            )
    
    if cfg.provider == "siliconflow":
        messages = fix_messages_for_siliconflow(messages)
    kwargs.pop("response_format", None)

    params = {
        "model": kwargs.pop("model", getattr(cfg, "model", None)),
        "messages": messages,
        "temperature": kwargs.pop("temperature", getattr(cfg, "temperature", 0.7)),
    }
    if "max_tokens" in kwargs:
        params["max_tokens"] = kwargs.pop("max_tokens")
    params.update(kwargs)
    params = {k: v for k, v in params.items() if v is not None}

    try:
        # 使用新版本的 OpenAI API (>=1.0.0)
        # 注意：这里使用的是 client.chat.completions.create，不是 openai.ChatCompletion.create
        response = client.chat.completions.create(**params)
        
        # 转换为旧格式以保持兼容性
        return {
            "choices": [{
                "message": {
                    "content": response.choices[0].message.content,
                    "role": response.choices[0].message.role
                }
            }]
        }
    except AttributeError as e:
        error_msg = str(e)
        if "ChatCompletion" in error_msg or "chat.completions" in error_msg:
            raise RuntimeError(
                "OpenAI API 版本不兼容。请确保：\n"
                "1. 已安装 openai>=1.0.0：pip install --upgrade openai\n"
                "2. 代码使用 client.chat.completions.create 而不是 openai.ChatCompletion.create\n"
                "3. 重启 Streamlit 应用以清除缓存\n"
                f"原始错误: {error_msg}"
            ) from e
        raise
    except Exception as e:
        error_msg = str(e)
        # 检查是否是 OpenAI SDK 的版本兼容性错误
        if "ChatCompletion" in error_msg and "no longer supported" in error_msg:
            raise RuntimeError(
                "OpenAI API 版本不兼容。检测到旧版本的 API 调用方式。\n"
                "解决方案：\n"
                "1. 升级 openai 包：pip install --upgrade openai\n"
                "2. 确保代码使用 client.chat.completions.create\n"
                "3. 完全重启 Streamlit 应用（停止所有进程并重新启动）\n"
                f"原始错误: {error_msg}"
            ) from e
        # 重新抛出异常，保留原始错误信息
        raise
