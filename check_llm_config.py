"""
检查LLM配置和连接性
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载.env文件
ROOT = Path(__file__).resolve().parent
for cand in (ROOT / ".env", ROOT / "app" / ".env", Path.cwd() / ".env"):
    if cand.exists():
        load_dotenv(dotenv_path=cand, override=True)
        print(f"[INFO] 已加载.env文件: {cand}")
        break

print("\n" + "="*60)
print("LLM配置检查")
print("="*60)

# 检查环境变量
siliconflow_key = os.getenv("SILICONFLOW_API_KEY")
openai_key = os.getenv("OPENAI_API_KEY")

print(f"\n[1] 环境变量检查:")
print(f"  - SILICONFLOW_API_KEY: {'已配置' if siliconflow_key else '未配置'}")
print(f"  - OPENAI_API_KEY: {'已配置' if openai_key else '未配置'}")

if siliconflow_key:
    print(f"  - SILICONFLOW_API_KEY长度: {len(siliconflow_key)}")
    print(f"  - SILICONFLOW_API_KEY前10字符: {siliconflow_key[:10]}...")
if openai_key:
    print(f"  - OPENAI_API_KEY长度: {len(openai_key)}")
    print(f"  - OPENAI_API_KEY前10字符: {openai_key[:10]}...")

# 尝试获取客户端
print(f"\n[2] 尝试获取LLM客户端:")
try:
    from backend.services.ai_client import get_client_and_cfg
    client, cfg = get_client_and_cfg()
    
    if cfg and cfg.api_key:
        print(f"  [OK] 客户端获取成功")
        print(f"  - Provider: {cfg.provider}")
        print(f"  - Model: {cfg.model}")
        print(f"  - Base URL: {cfg.base_url}")
        print(f"  - Temperature: {cfg.temperature}")
        print(f"  - API Key长度: {len(cfg.api_key)}")
    else:
        print(f"  [FAIL] 客户端获取失败: API Key未配置")
        print(f"  - cfg对象: {cfg}")
        if cfg:
            print(f"  - cfg.api_key: {cfg.api_key}")
except Exception as e:
    print(f"  ✗ 客户端获取失败: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("检查完成")
print("="*60)



