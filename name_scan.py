# -*- coding: utf-8 -*-
from pathlib import Path
from backend.services import resume_parser as rp
root = Path('data/uploads')
wrong = []
for path in root.iterdir():
    if path.suffix.lower() not in {'.pdf', '.docx', '.txt'}:
        continue
    try:
        text, _ = rp.parse_one_to_text(path)
    except Exception as e:
        continue
    name = rp.infer_candidate_name(text, path.name)
    bad_keywords = ['奖', '学士', '全国', '完成', '项目', '成交', '学生', '理竞赛', '优秀']
    if not name or any(bad in name for bad in bad_keywords):
        wrong.append((path.name, name))
print('wrong count', len(wrong))
for item in wrong[:50]:
    print(item)
