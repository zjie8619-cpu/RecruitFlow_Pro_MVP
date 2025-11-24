# -*- coding: utf-8 -*-
from pathlib import Path
from backend.services import resume_parser as rp
root = Path('data/uploads')
target_keywords = ['年经验', '程度', '致力于创作']
for path in root.iterdir():
    if path.suffix.lower() not in {'.pdf', '.docx', '.txt'}:
        continue
    try:
        text, _ = rp.parse_one_to_text(path)
    except Exception:
        continue
    name = rp.infer_candidate_name(text, path.name)
    if any(key in (name or '') for key in target_keywords):
        print('MATCH', path.name, '->', name)
        snippet = (text or '')[:200].replace('\n', ' ')
        print('TEXT:', snippet)
