# -*- coding: utf-8 -*-
import os

env_content = """SILICONFLOW_API_KEY=sk-iutztqilqfhhqphfllqyqpfxmegwievllyiyrqbbchskujmo
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
AI_MODEL=Qwen/Qwen2.5-32B-Instruct
AI_TEMPERATURE=0.7
"""

# 使用UTF-8无BOM写入
with open('.env', 'w', encoding='utf-8') as f:
    f.write(env_content)

print("已创�?env文件（UTF-8无BOM�?)
print("文件内容�?)
with open('.env', 'r', encoding='utf-8') as f:
    print(f.read())

