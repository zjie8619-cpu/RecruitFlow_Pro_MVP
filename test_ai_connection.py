# -*- coding: utf-8 -*-
"""测试AI连接"""
import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from backend.services.ai_client import get_client_and_cfg

try:
    print("[TEST] 正在测试AI连接...")
    client, cfg = get_client_and_cfg()
    
    print(f"[OK] 配置读取成功：")
    print(f"   Provider: {cfg.provider}")
    print(f"   Model: {cfg.model}")
    print(f"   Base URL: {cfg.base_url}")
    print(f"   Key前缀: {cfg.api_key[:15]}...")
    
    print(f"\n[TEST] 正在调用AI...")
    res = client.chat.completions.create(
        model=cfg.model,
        messages=[{"role":"user","content":"只返回 OK"}],
        temperature=0,
        max_tokens=10
    )
    result = res.choices[0].message.content.strip()
    print(f"[SUCCESS] AI 连通性测试成功！")
    print(f"   AI 返回：{result}")
except Exception as e:
    error_msg = str(e)
    print(f"[FAILED] 测试失败：{error_msg}")
    if "Key" in error_msg or "未检测" in error_msg:
        print("[TIP] 请检查 .env 文件中的 API Key 配置")
    elif "401" in error_msg or "403" in error_msg:
        print("[TIP] API Key 无效或已过期")
    elif "404" in error_msg:
        print("[TIP] 模型不存在，尝试更换为其他模型")
    else:
        print("[TIP] 请检查网络连接和配置")

