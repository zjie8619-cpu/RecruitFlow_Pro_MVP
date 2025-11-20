"""Utility helpers for cleaning JD-related free text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

COMPETITION_JOB_KEYWORDS: Tuple[str, ...] = (
    "竞赛",
    "教练",
    "教研",
    "教师",
    "讲师",
    "辅导",
    "奥赛",
)

COMPETITION_TERMS: Tuple[str, ...] = (
    "竞赛",
    "奥赛",
    "奥林匹克",
    "命题",
    "LaTeX",
    "latex",
    "教研",
    "教学",
    "教案",
    "题库",
)


@dataclass
class JD:
    """Minimal JD structure used for short文本渲染."""

    mission: str = ""
    responsibilities: str = ""
    requirements: str = ""
    plus: str = ""
    exclude: str = ""


def _is_competition_job(job: str | None) -> bool:
    if not job:
        return False
    text = job.lower()
    return any(keyword.lower() in text for keyword in COMPETITION_JOB_KEYWORDS)


def _split_segments(text: str) -> List[str]:
    normalized = (
        text.replace("；", "||")
        .replace(";", "||")
        .replace("，", "||")
        .replace(",", "||")
        .replace("。", "||")
        .replace("\n", "||")
    )
    parts = [seg.strip() for seg in normalized.split("||")]
    return [seg for seg in parts if seg]


def _filter_segments(segments: Iterable[str], banned_terms: Iterable[str]) -> List[str]:
    banned = tuple(banned_terms)
    out: List[str] = []
    for seg in segments:
        lowered = seg.lower()
        if any(term.lower() in lowered for term in banned):
            continue
        out.append(seg)
    return out


def strip_competition_terms(text: str, job: str | None = None) -> str:
    """
    Remove competition-only phrases when岗位不是竞赛/教研类.
    """

    if not text:
        return ""
    if _is_competition_job(job):
        return text.strip()

    segments = _split_segments(text)
    filtered = _filter_segments(segments, COMPETITION_TERMS)
    return "；".join(filtered)


def sanitize_for_job(job: str, evidence: str, summary: str) -> tuple[str, str]:
    """
    Guard rail used by matcher tests: remove竞赛术语 for非教培岗位.
    """

    is_competition = _is_competition_job(job)
    banned = COMPETITION_TERMS if not is_competition else ()

    def _sanitize(text: str) -> str:
        if not text:
            return ""
        if not banned:
            return text.strip()
        segments = _split_segments(text)
        filtered = _filter_segments(segments, banned)
        return "；".join(filtered)

    return _sanitize(evidence), _sanitize(summary)

# -*- coding: utf-8 -*-
"""
# text_rules.py — 文本推断与格式化规则(已修复缩进 & 语法 & 逻辑)
"""
import re
from typing import List, Tuple, Literal
from dataclasses import dataclass
# ----------------------------
# 基础工具函数
# ----------------------------
def safe_strip(text: str) -> str:
    """安全去掉空白"""
    if not isinstance(text, str):
        return ""
    return text.strip()

def is_empty(text: str) -> bool:
    """判断是否为空文本"""
    return text is None or str(text).strip() == ""
# ----------------------------
# format_list: 将列表转成 ① ② ③ 排序文本
# ----------------------------
def format_list(items: List[str]) -> str:
    """
    将列表格式化为可读编号文本(① ② ③ …)
    """
    if not items:
        return ""
    bullets = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨"]
    formatted = []
    for i, item in enumerate(items):
        bullet = bullets[i] if i < len(bullets) else f"{i+1}."
        formatted.append(f"{bullet} {item.strip()}")
    return "\n".join(formatted)
# ----------------------------
# infer_job_family: 行业与岗位家族推断
# ----------------------------
def infer_job_family(job_name: str) -> str:
    """
    根据岗位名推断岗位家族
    返回标准化值:coach/teacher/sales/engineer_dev/generic
    """
    if not isinstance(job_name, str):
        return "generic"
    name = job_name.lower()
    # 优先判断竞赛教练相关岗位
    if "生物竞赛" in name or "数竞" in name or "奥赛" in name or "竞赛教练" in name:
        return "coach"
    # 技术类关键词
    engineer_keywords = ["开发", "工程师", "前端", "后端", "java", "python", "测试工程师", "测试", "qa", "全栈", "架构师", "golang", "go", "node", "react", "vue", "typescript", "后端开发", "前端开发"]
    # 销售类关键词(需要优先匹配,避免被其他类别误判)
    sales_keywords = ["课程顾问", "招生顾问", "销售", "招生", "电销", "咨询顾问", "售前"]
    # 教师类关键词
    teacher_keywords = ["老师", "班主任", "任课教师", "讲师", "授课", "教研"]
    # 教练类关键词
    coach_keywords = ["竞赛", "奥赛", "国一", "教练", "竞赛教师", "解题训练", "赛题"]
    # 按优先级检查:销售类优先(因为"课程顾问"可能被误判为其他类别)
    if any(k in name for k in sales_keywords):
        return "sales"
    if any(k in name for k in engineer_keywords):
        return "engineer_dev"
    if any(k in name for k in teacher_keywords):
        return "teacher"
    if any(k in name for k in coach_keywords):
        return "coach"
    return "generic"
# ----------------------------
# extract_keywords: 从文本提取关键词
# ----------------------------
def extract_keywords(text: str) -> List[str]:
    """
    提取关键词(数字+文字、动词短语等)
    """
    if not isinstance(text, str):
        return []
    patterns = [
        r"[0-9]+年经验",
        r"[0-9]+年以上",
        r"[0-9]+个月",
        r"熟悉[^\s,.;;]+",
        r"掌握[^\s,.;;]+",
        r"能独立[^\s,.;;]+",
        r"负责[^\s,.;;]+",
        r"精通[^\s,.;;]+",
    ]
    results = []
    for p in patterns:
        results += re.findall(p, text)
    return list(set(results))

# ----------------------------
# clean_text: 通用清洗
# ----------------------------
def clean_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
# ----------------------------
# parse_paragraphs: 按句拆分
# ----------------------------
def parse_paragraphs(text: str) -> List[str]:
    if not isinstance(text, str):
        return []
    parts = re.split(r"[.!?;;]", text)
    return [p.strip() for p in parts if p.strip()]

# ----------------------------
# validate_text: 过滤异常文本
# ----------------------------
def validate_text(text: str) -> str:
    """发现乱码、空文本则提示人工检查"""
    if is_empty(text):
        return "该段文本为空,请检查来源."
    if re.search(r"[^\u4e00-\u9fa5a-zA-Z0-9,.;;,.!?!?\s]", text):
        return "该文本存在疑似乱码,请人工检查."
    return ""

# ----------------------------
# merge_texts: 多段落合并
# ----------------------------
def merge_texts(paragraphs: List[str]) -> str:
    """将多段文本按行合并"""
    paragraphs = [p for p in paragraphs if p]
    return "\n".join(paragraphs)
# ----------------------------
# 主入口:normalize_text
# ----------------------------
def normalize_text(text: str) -> str:
    """
    文本→清洗→拆句→去异常→合并
    """
    if text is None:
        return ""
    raw = clean_text(text)
    paras = parse_paragraphs(raw)
    valid_paras = []
    for p in paras:
        err = validate_text(p)
        if not err:
            valid_paras.append(p)
    return merge_texts(valid_paras)

# ----------------------------
# 兼容函数:strip_competition_terms
# ----------------------------
def strip_competition_terms(text: str, clean_family: str = "generic") -> str:
    """
    去除描述中的比赛词汇,使之更通用
    Args:
        text: 要处理的文本
        clean_family: 岗位家族类型(coach/teacher/sales/engineer_dev/generic)
    Returns:
        清理后的文本
    """
    if not isinstance(text, str):
        return ""
    # 如果是教练或教师岗位,保留竞赛相关词汇
    if clean_family in {"coach", "teacher"}:
        return text.strip()
    # 竞赛相关术语列表
    COMPETITION_TERMS = [
        "生物竞赛",
        "化学竞赛",
        "数学竞赛",
        "信息竞赛",
        "物理竞赛",
        "奥林匹克",
        "国赛",
        "省赛",
        "NOI",
        "CSP",
        "AMC",
        "IOI",
        "IMO",
        "奥赛",
        "竞赛",
    ]
    cleaned = text
    for term in COMPETITION_TERMS:
        cleaned = cleaned.replace(term, "")
    # 清理多余空格
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()

# ----------------------------
# 兼容函数:sanitize_for_job
# ----------------------------
def sanitize_for_job(
    job_name: str, 
    evidence_text: str, 
    summary_text: str, 
    mode: str = "auto"
) -> Tuple[str, str]:
    """
    针对具体岗位进行"证据/简评"的降噪清洗
    Args:
        job_name: 岗位名称
        evidence_text: 证据文本
        summary_text: 简评文本
        mode: 清洗模式(auto/strict/education)
    Returns:
        (cleaned_evidence, cleaned_summary) 元组
    """
    if not isinstance(evidence_text, str):
        evidence_text = ""
    if not isinstance(summary_text, str):
        summary_text = ""
    # 自动判断模式
    if mode == "auto":
        job_lower = (job_name or "").lower()
        education_keywords = ["教师", "教练", "数学", "语文", "英语", "学科", "讲师", "班主任", "教研", "竞赛教练", "课程顾问", "招生顾问"]
        sales_keywords = ["销售", "置业", "电销"]
        if any(k in job_lower for k in education_keywords):
            mode = "education"
        elif any(k in job_lower for k in sales_keywords):
            mode = "strict"
        else:
            mode = "education"  # 默认宽松模式
    # 基础清洗
    def _basic_clean(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        return text.strip()
    cleaned_evidence = _basic_clean(evidence_text)
    cleaned_summary = _basic_clean(summary_text)
    # 严格模式:去除竞赛相关词汇
    if mode == "strict":
        cleaned_evidence = strip_competition_terms(cleaned_evidence, "generic")
        cleaned_summary = strip_competition_terms(cleaned_summary, "generic")
    return cleaned_evidence, cleaned_summary

# ----------------------------
# 本文件 API 导出
# ----------------------------
__all__ = [
"format_list",
"infer_job_family",
"extract_keywords",
"clean_text",
"parse_paragraphs",
"validate_text",
"normalize_text",
"strip_competition_terms",
"sanitize_for_job",
]
