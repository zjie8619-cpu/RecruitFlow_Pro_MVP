# -*- coding: utf-8 -*-
from pathlib import Path
from dotenv import load_dotenv
import os

env_path = Path('.env')
print(f'文件存在: {env_path.exists()}')
print(f'文件路径: {env_path.absolute()}')

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    key = os.getenv('SILICONFLOW_API_KEY')
    print(f'读取到Key: {"�? if key else "�?}')
    if key:
        print(f'Key长度: {len(key)}')
        print(f'Key前缀: {key[:15]}...')
    else:
        print('尝试直接读取文件内容...')
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f'文件内容�?00字符: {content[:100]}')

