import re
from pathlib import Path
from typing import List, Tuple
import yaml

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "job_rules.yaml"

def _load_rules():
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

_RULES = _load_rules()

def _which_family(job_name: str) -> str:
    """根据职位名称识别 family（销售/竞赛教练/...），未命中返回空字符串。"""
    job_name = (job_name or "").lower()
    families = _RULES.get("families", {})
    for fam, cfg in families.items():
        for alias in cfg.get("aliases", []):
            if alias.lower() in job_name:
                return fam
    return ""

def _compile_keywords(words: List[str]) -> re.Pattern:
    if not words:
        # 永不匹配
        return re.compile(r"(?!x)x")
    # 按词边界做较为宽松的中文匹配
    joined = "|".join(map(re.escape, words))
    return re.compile(joined)

def sanitize_for_job(job_name: str, evidence_text: str, summary_text: str) -> Tuple[str, str]:
    """
    针对具体岗位进行"证据/简评"的降噪清洗：
      1) 对"销售/课程顾问"等家族，去掉任何含有竞赛/学术研究类词的句子
      2) 同时要求保留的句子至少包含销售相关词（allow_only_if_contains_any）
      3) 其它家族保持不变
    """
    family = _which_family(job_name)
    if not family:
        return evidence_text, summary_text

    fam_cfg = _RULES["families"][family]
    banned_re = _compile_keywords(fam_cfg.get("banned_keywords", []))
    must_re   = _compile_keywords(fam_cfg.get("allow_only_if_contains_any", []))

    def _clean_block(text: str) -> str:
        if not text:
            return text
        # 按句号/分号/换行切分，逐句过滤
        parts = re.split(r"[；;。\n]+", text)
        kept = []
        for p in parts:
            t = p.strip()
            if not t:
                continue
            # 有禁用词就直接丢弃
            if banned_re.search(t):
                continue
            # 对"销售家族"要求至少命中 must_re 之一（防止 LLM 乱编"竞赛证据"）
            if family == "销售" and not must_re.search(t):
                continue
            kept.append(t)
        return "；".join(kept) if kept else ""

    return _clean_block(evidence_text), _clean_block(summary_text)

