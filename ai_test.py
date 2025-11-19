
# -*- coding: utf-8 -*-
import os
import sys
import openai
from backend.services.ai_client import chat_completion, AIConfig
from dotenv import load_dotenv

# 设置输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

# 尝试优先用环境变量
key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("OPENAI_API_KEY")
if not key:
    print("[ERROR] 未检测到环境变量 SILICONFLOW_API_KEY 或 OPENAI_API_KEY。请先配置 .env 文件。")
    raise SystemExit

base = os.getenv("SILICONFLOW_BASE_URL") or "https://api.openai.com/v1"
model = os.getenv("AI_MODEL") or os.getenv("SILICONFLOW_MODEL") or "gpt-4o-mini"

print("[OK] 已读取配置：")
print(f"   Key前缀: {key[:15]}...")
print(f"   Base URL: {base}")
print(f"   模型: {model}")
print(f"\n[TEST] 正在测试AI连通性...")

openai.api_key = key
openai.api_base = base
cfg = AIConfig(
    provider="siliconflow" if os.getenv("SILICONFLOW_API_KEY") else "openai",
    api_key=key,
    base_url=base,
    model=model,
    temperature=0.0,
)
client = openai

try:
    res = chat_completion(
        client,
        cfg,
        messages=[{"role":"user","content":"只返回 OK"}],
        temperature=0,
        max_tokens=10
    )
    result = res["choices"][0]["message"]["content"].strip()
    print(f"[SUCCESS] AI 连通性测试成功！")
    print(f"   AI 返回：{result}")
except Exception as e:
    error_msg = str(e)
    print(f"[FAILED] 调用失败：{error_msg}")
    if "401" in error_msg or "403" in error_msg:
        print("[TIP] API Key 无效或已过期，请检查 .env 中的 Key 是否正确")
    elif "404" in error_msg:
        print("[TIP] 模型不存在或未开通，请检查 .env 中的 AI_MODEL，尝试更换为 Qwen2.5-32B-Instruct")
    elif "timeout" in error_msg.lower():
        print("[TIP] 网络连接问题，检查网络是否放行 api.siliconflow.cn")
    else:
        print("[TIP] 请检查 .env 配置和网络连接")


