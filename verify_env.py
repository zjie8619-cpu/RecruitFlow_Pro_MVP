# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# 设置输出编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 检查app/.env
app_env = Path('app/.env')
root_env = Path('.env')

print(f'app/.env存在: {app_env.exists()}')
print(f'根目�?env存在: {root_env.exists()}')

# 从app目录加载
if app_env.exists():
    load_dotenv(dotenv_path=app_env)
    print('已从app/.env加载')
elif root_env.exists():
    load_dotenv(dotenv_path=root_env)
    print('已从根目�?env加载')
else:
    load_dotenv()
    print('使用默认load_dotenv()')

key = os.getenv('SILICONFLOW_API_KEY')
print(f'Key已读�? {"OK" if key and key.startswith("sk-") else "FAIL"}')
if key:
    print(f'Key前缀: {key[:15]}...')
    print(f'Base URL: {os.getenv("SILICONFLOW_BASE_URL", "未设�?)}')
    print(f'Model: {os.getenv("AI_MODEL", "未设�?)}')

