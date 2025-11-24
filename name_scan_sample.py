# -*- coding: utf-8 -*-
from pathlib import Path
from backend.services import resume_parser as rp
root = Path('data/uploads')
wrong = []
for idx, path in enumerate(root.iterdir()):
    if idx > 60:
        break
    if path.suffix.lower() not in {'.pdf', '.docx', '.txt'}:
        continue
    try:
        text, _ = rp.parse_one_to_text(path)
    except Exception as e:
        continue
    name = rp.infer_candidate_name(text, path.name)
    if not name or any(bad in name for bad in ['奖','竞赛','完成','项目','成交']):
        wrong.append((path.name, name))
print('checked', idx+1)
print('wrong count', len(wrong))
for item in wrong:
    print(item)
