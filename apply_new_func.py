from pathlib import Path

path = Path("backend/services/ai_matcher.py")
new_func = Path("tmp_new_func.py").read_text(encoding="utf-8")
text = path.read_text(encoding="utf-8")
start = text.index("def ai_score_one")
end = text.index("def ai_match_resumes_df")
updated = text[:start] + new_func + "\n\n" + text[end:]
path.write_text(updated, encoding="utf-8")

