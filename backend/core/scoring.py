from typing import Dict, List, Tuple
from backend.utils.text_utils import contains_any

def _ratio_hits(text: str, kws: List[str]) -> float:
    if not kws: return 0.0
    hits = contains_any(text, kws)
    valid = len([k for k in kws if k])
    return len(hits) / max(valid, 1)

def _stability(years: float, companies: str) -> float:
    if years <= 0: return 0.0
    c = max(len([x for x in (companies or '').split('/') if x.strip()]), 1)
    return min(years/(c*3.0), 1.0)

def _growth(text: str) -> float:
#     kws = ["复盘","证书","学习","培训","带队","负责","主导","从0到1","增长","ROI","转化"]
    return min(1.0, len(contains_any(text, kws))/5.0)

def compute_scores(job_rule: Dict, row: Dict, weights: Dict[str,float], whitelist: List[str], evidence_max: int=3) -> Tuple[Dict, List[str], float]:
    must = [x.strip() for x in (job_rule.get('must_have') or '').split(';') if x.strip()]
    nice = [x.strip() for x in (job_rule.get('nice_to_have') or '').split(';') if x.strip()]
    exclude = [x.strip() for x in (job_rule.get('exclude_keywords') or '').split(';') if x.strip()]
    min_years = float(job_rule.get('min_years') or 0)

    text_all = ' '.join([str(row.get('skills','')), str(row.get('projects','')), str(row.get('text_raw','')), str(row.get('companies',''))])

    must_ratio = _ratio_hits(text_all, must)
    nice_ratio = _ratio_hits(text_all, nice)
    skill_fit  = 0.75*must_ratio + 0.25*nice_ratio

    excluded_hits = contains_any(text_all, exclude)
    if excluded_hits: skill_fit *= 0.5

    years = float(row.get('years') or 0)
    exp_year = min(max((years - min_years + 1)/5.0, 0), 1)
    wl_ratio = _ratio_hits(text_all, whitelist)
    exp_rel = 0.7*exp_year + 0.3*wl_ratio

    stability = _stability(years, row.get('companies',''))
    growth    = _growth(text_all)

    confidence = min(1.0, 0.5 + 0.4*must_ratio - 0.3*len(excluded_hits))

    total = round(weights['skill_fit']*skill_fit + weights['exp_relevance']*exp_rel + weights['stability']*stability + weights['growth']*growth, 4)

    evidence=[]
    for kw in must + nice:
#         if kw and kw in text_all: evidence.append(f"命中:{kw}")
        if len(evidence)>=evidence_max: break
#     if excluded_hits: evidence.append("触发排除:" + ",".join(excluded_hits))

    return {'score_total': total,'skill_fit': round(skill_fit,4),'exp_relevance': round(exp_rel,4),'stability': round(stability,4),'growth': round(growth,4)}, evidence, round(confidence,4)

