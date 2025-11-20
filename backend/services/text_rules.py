import re
from pathlib import Path
from typing import List, Tuple, Literal
import yaml

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "configs" / "job_rules.yaml"

def _load_rules():
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

_RULES = _load_rules()

# -------- Job Family 推断（用于 JD/匹配统一使用） --------
JobFamily = Literal["coach", "teacher", "sales", "engineer_dev", "generic"]

def infer_job_family(job_name: str) -> str:
    """
    返回标准化 job family：coach/teacher/sales/engineer_dev/generic
    先基于关键词快速判定；未命中再回退到 YAML families。
    """
    t = (job_name or "").lower()

    engineer_keywords = ["开发", "工程师", "前端", "后端", "java", "python", "测试工程师", "测试", "qa", "全栈", "架构师", "golang", "go", "node", "react", "vue", "typescript", "后端开发", "前端开发"]
    sales_keywords = ["销售", "课程顾问", "招生", "电销", "咨询顾问", "售前"]
    teacher_keywords = ["老师", "班主任", "任课教师", "讲师", "授课", "教研"]
    coach_keywords = ["竞赛", "奥赛", "国一", "教练", "竞赛教师", "解题训练", "赛题"]

    if any(k in t for k in engineer_keywords):
        return "engineer_dev"
    if any(k in t for k in sales_keywords):
        return "sales"
    if any(k in t for k in teacher_keywords):
        return "teacher"
    if any(k in t for k in coach_keywords):
        return "coach"

    # 回退到 YAML families（例如“销售/竞赛教练”一类）
    fam = _which_family(job_name)
    if fam in ("销售",):
        return "sales"
    if fam in ("教师", "老师"):
        return "teacher"
    if fam in ("竞赛教练",):
        return "coach"
    return "generic"

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
      4) 如果清洗后内容为空，返回中性描述（避免完全空白）
    """
    family = _which_family(job_name)
    if not family:
        return evidence_text, summary_text

    fam_cfg = _RULES["families"][family]
    banned_re = _compile_keywords(fam_cfg.get("banned_keywords", []))
    must_re   = _compile_keywords(fam_cfg.get("allow_only_if_contains_any", []))

    # 默认中性描述（当所有内容被过滤时使用）
    default_evidence = "候选人具备一定的行业经验和沟通能力。"
    default_summary = "候选人具备基本的职业素养和沟通能力。"

    def _clean_block(text: str, default: str = "") -> str:
        if not text:
            return default if default else text
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
        result = "；".join(kept) if kept else ""
        # 如果清洗后为空，使用默认描述
        if not result and default:
            return default
        return result

    cleaned_evidence = _clean_block(evidence_text, default_evidence)
    cleaned_summary = _clean_block(summary_text, default_summary)
    
    return cleaned_evidence, cleaned_summary


# -------- 竞赛相关词汇清洗（用于非 coach/teacher 岗位 JD 文案） --------
COMPETITION_KEYWORDS = [
    "竞赛", "奥赛", "国一", "省一", "解题训练", "刷题",
    "赛题", "LaTeX", "latex", "带队", "集训队", "教案", "命题", "赛题解析"
]

def strip_competition_terms(text: str, job_family: JobFamily) -> str:
    """非教练/教师岗位，去掉/弱化竞赛相关措辞。"""
    if not text:
        return text
    if job_family in {"coach", "teacher"}:
        return text
    result = text
    for kw in COMPETITION_KEYWORDS:
        result = result.replace(kw, "")
    # 兼容不同破折号/连接符的“国一/省一”等写法
    result = re.sub(r"国[\\-—–]?一", "", result)
    result = re.sub(r"省[\\-—–]?一", "", result)
    # 折叠多余分隔符（/ ｜ 、 ； 空格 破折号）
    result = re.sub(r"[\\/｜|、；;—\-]{2,}", "、", result)
    # 去掉分隔符周围多余空白
    result = re.sub(r"\s*([\\/｜|、；;—\-])\s*", r"\1", result)
    # 去掉开头/结尾分隔符或破折号
    result = re.sub(r"^[\\/｜|、；;—\-]+", "", result)
    result = re.sub(r"[\\/｜|、；;—\-]+$", "", result)
    # 如果仅剩分隔符或空字符，置为空
    if re.fullmatch(r"[\\/｜|、；;—\-]*", result):
        return ""
    # 规范空白
    result = re.sub(r"\s{2,}", " ", result).strip()
    return result

