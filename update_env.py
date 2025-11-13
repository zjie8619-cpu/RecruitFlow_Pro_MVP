# -*- coding: utf-8 -*-
env_content = """SILICONFLOW_API_KEY=sk-iutztqilqfhhqphfllqyqpfxmegwievllyiyrqbbchskujmo
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
AI_MODEL=Qwen2.5-32B-Instruct
AI_TEMPERATURE=0.7
"""

# 写入根目录
with open('.env', 'w', encoding='utf-8') as f:
    f.write(env_content)

# 复制到app目录
import shutil
shutil.copy('.env', 'app/.env')

print("已更新.env文件（根目录和app目录）")
print("模型: Qwen2.5-32B-Instruct")

