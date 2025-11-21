"""
Lightweight heuristic matcher used when the heavy AI pipeline is unavailable.
It scores resumes against a JD text and returns a dataframe with scoring columns
expected by the Streamlit UI.
"""

from __future__ import annotations

import io
import json
import math
import re
import sys
import textwrap
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import pandas as pd

from backend.services.ai_insights import FALLBACK_RESPONSE, generate_ai_insights
from backend.services.text_rules import sanitize_for_job, strip_competition_terms


SPLIT_PATTERN = re.compile(r"[。.!?；;，,\n]+")
WORD_PATTERN = re.compile(r"[A-Za-z0-9\u4e00-\u9fa5]{2,}")

GROWTH_KEYWORDS = ("学习", "成长", "复盘", "改进", "自我驱动", "迭代")
STABILITY_KEYWORDS = ("稳定", "长期", "连续", "任职", "留任", "年度")

EDUCATION_BOOST_RULES = [
    (("博士", "PhD", "Doctor", "博士后"), 12, 10),
    (("硕士", "Master", "研究生"), 8, 6),
    (("本科", "学士", "Bachelor"), 4, 3),
]

DIME_META = {
    "技能匹配度": {"max": 30.0, "weight": 0.30},
    "经验相关性": {"max": 30.0, "weight": 0.30},
    "成长潜力": {"max": 20.0, "weight": 0.20},
    "稳定性": {"max": 20.0, "weight": 0.20},
}

DOMAIN_KEYWORDS = {
    "物理", "竞赛", "教练", "奥赛", "imo", "cupt", "教学", "教研", "实验",
    "科研", "课程", "课堂", "教材", "latex", "教案", "辅导", "学生", "赛题"
}


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [tok.lower() for tok in WORD_PATTERN.findall(text)]


def _top_keywords(tokens: Sequence[str], limit: int = 25) -> set[str]:
    freq: dict[str, int] = {}
    for tok in tokens:
        freq[tok] = freq.get(tok, 0) + 1
    sorted_tokens = sorted(freq.items(), key=lambda item: item[1], reverse=True)
    return {tok for tok, _ in sorted_tokens[:limit]}


def _length_score(text_len: int) -> float:
    if text_len >= 4500:
        return 95
    if text_len >= 3000:
        return 88
    if text_len >= 2000:
        return 80
    if text_len >= 1200:
        return 68
    if text_len >= 600:
        return 55
    return 45


def _keyword_overlap_score(resume_tokens: set[str], job_tokens: set[str]) -> float:
    if not job_tokens:
        return 75
    overlap = len(resume_tokens & job_tokens)
    ratio = overlap / max(len(job_tokens), 1)
    # scale ratio (0-1) into 45-98
    return max(45.0, min(98.0, 45.0 + ratio * 70.0))


def _count_keywords(text: str, keywords: Iterable[str]) -> int:
    lowered = text.lower()
    return sum(lowered.count(word.lower()) for word in keywords)


def _growth_score(text: str) -> float:
    hits = _count_keywords(text, GROWTH_KEYWORDS)
    if hits >= 6:
        return 92
    if hits >= 4:
        return 82
    if hits >= 2:
        return 73
    if hits >= 1:
        return 64
    return 55


def _stability_score(text: str) -> float:
    hits = _count_keywords(text, STABILITY_KEYWORDS)
    if hits >= 5:
        return 90
    if hits >= 3:
        return 78
    if hits >= 1:
        return 68
    return 60


def _collect_evidence(resume_text: str, job_tokens: set[str]) -> str:
    if not resume_text:
        return ""
    segments = [seg.strip() for seg in SPLIT_PATTERN.split(resume_text) if seg.strip()]
    if not segments:
        return ""

    scored: List[Tuple[int, str]] = []
    lowered_tokens = {tok.lower() for tok in job_tokens}
    for seg in segments:
        seg_tokens = _tokenize(seg)
        overlap = len(lowered_tokens & set(seg_tokens))
        if overlap:
            scored.append((overlap, seg))

    scored.sort(key=lambda item: item[0], reverse=True)
    evidence_segments = [seg for _, seg in scored[:3]] or segments[:2]
    return "；".join(evidence_segments)


def _education_boost(text: str) -> tuple[float, float]:
    """Return (skill_boost, growth_boost) based on education level mentioned."""
    lowered = text.lower()
    for keywords, skill_boost, growth_boost in EDUCATION_BOOST_RULES:
        if any(keyword.lower() in lowered for keyword in keywords):
            return float(skill_boost), float(growth_boost)
    return 0.0, 0.0


def _domain_boost(resume_tokens: set[str], jd_tokens: set[str]) -> float:
    """Give extra skill points when resume explicitly提到 JD 关键术语。"""
    keywords = DOMAIN_KEYWORDS | {tok for tok in jd_tokens if tok in DOMAIN_KEYWORDS}
    hits = len(resume_tokens & keywords)
    if hits == 0:
        return 0.0
    return min(15.0, 4.0 * hits)


def _normalize_score(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _parse_ai_json(raw_content: str) -> dict:
    """
    解析大模型返回的 JSON 内容，容错处理 Markdown 或额外文本。
    """
    if not raw_content:
        raise ValueError("empty content")

    candidates: List[str] = [raw_content.strip()]

    # 去除常见的代码块包装
    if candidates[0].startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*", "", candidates[0]).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
        candidates.append(stripped)

    # 截取第一个大括号到最后一个大括号之间的内容
    start = raw_content.find("{")
    end = raw_content.rfind("}")
    if 0 <= start < end:
        candidates.append(raw_content[start : end + 1])

    for cand in candidates:
        try:
            return json.loads(cand)
        except Exception:
            continue
    raise ValueError("unable to parse AI JSON response")


def _short_eval(total: float, skill: float, exp: float, growth: float) -> str:
    return (
        f"总体 {total:.0f} 分｜技能 {skill:.0f}｜经验 {exp:.0f}｜"
        f"成长 {growth:.0f}"
    )


def _format_short_eval_struct(short_eval: Dict[str, Any] | None) -> str:
    if not isinstance(short_eval, dict):
        short_eval = {}
    strengths = short_eval.get("core_strengths") or short_eval.get("strengths") or []
    weaknesses = short_eval.get("core_weaknesses") or short_eval.get("weaknesses") or []
    match_level = short_eval.get("match_level") or "无法评估"
    match_reason = short_eval.get("match_reason") or ""

    parts = ["【优势】"]
    if strengths:
        for idx, value in enumerate(strengths, 1):
            parts.append(f"{idx}. {value}")
    else:
        parts.append("1. 无明显优势")

    parts.append("")
    parts.append("【劣势】")
    if weaknesses:
        for idx, value in enumerate(weaknesses, 1):
            parts.append(f"{idx}. {value}")
    else:
        parts.append("1. 无明显劣势")

    parts.append("")
    parts.append("【匹配度】")
    reason = f"{match_level} {match_reason}".strip()
    parts.append(reason or match_level or "无法评估")

    return "\n".join(parts).strip()


def _trim_text(value: str, limit: int = 80) -> str:
    text = (value or "").strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def _format_reasoning_text(evidence_struct: Dict[str, Any]) -> str:
    if not isinstance(evidence_struct, dict):
        return ""

    lines: List[str] = []
    strengths = evidence_struct.get("strengths_reasoning_chain") or []
    weaknesses = evidence_struct.get("weaknesses_reasoning_chain") or []

    if strengths:
        lines.append("【优势】")
        for idx, item in enumerate(strengths, 1):
            if not isinstance(item, dict):
                continue
            conclusion = _trim_text(item.get("conclusion", ""), 24)
            actions = _trim_text(item.get("detected_actions", ""), 32)
            resume_evidence = _trim_text(item.get("resume_evidence", ""), 60)
            reasoning = _trim_text(item.get("ai_reasoning", ""), 40)
            segments = [
                conclusion,
                f"动作:{actions}" if actions else "",
                f"证据:{resume_evidence}" if resume_evidence else "",
                f"推断:{reasoning}" if reasoning else "",
            ]
            segments = [seg for seg in segments if seg]
            if segments:
                lines.append(f"{idx}. " + "｜".join(segments))

    if weaknesses:
        if lines:
            lines.append("")
        lines.append("【劣势】")
        for idx, item in enumerate(weaknesses, 1):
            if not isinstance(item, dict):
                continue
            conclusion = _trim_text(item.get("conclusion", ""), 24)
            gap = _trim_text(item.get("resume_gap", ""), 32)
            compare = _trim_text(item.get("compare_to_jd", ""), 60)
            reasoning = _trim_text(item.get("ai_reasoning", ""), 40)
            segments = [
                conclusion,
                f"缺口:{gap}" if gap else "",
                f"JD:{compare}" if compare else "",
                f"风险:{reasoning}" if reasoning else "",
            ]
            segments = [seg for seg in segments if seg]
            if segments:
                lines.append(f"{idx}. " + "｜".join(segments))

    return "\n".join(lines).strip()


def _heuristic_score_from_text(
    jd_text: str, resume_text: str, job_title: str = ""
) -> Dict[str, Any]:
    """
    当大模型打分失败时，使用本地启发式规则给出一个“还算合理”的评分，避免出现全 0 分。
    评分维度与前端展示保持一致：总分 / 技能匹配度 / 经验相关性 / 成长潜力 / 稳定性。
    """
    jd_clean = strip_competition_terms(jd_text or "", job_title or "")
    job_tokens = _top_keywords(_tokenize(jd_clean))

    resume_tokens = set(_tokenize(resume_text or ""))
    text_len = len(resume_text or "")

    # 技能匹配度：基于关键词重叠（岗位匹配度的核心指标）
    skill_score = _keyword_overlap_score(resume_tokens, job_tokens)
    
    # 经验相关性：结合文本长度和岗位匹配度（更关注岗位匹配）
    base_exp_score = _length_score(text_len)
    # 如果技能匹配度高，经验相关性也应该相应提高（岗位匹配度高）
    exp_match_boost = skill_score * 0.3  # 技能匹配度高的，经验相关性也高
    exp_score = _normalize_score(base_exp_score * 0.7 + exp_match_boost, 0, 100)
    
    growth_score = _growth_score(resume_text or "")
    stability_score = _stability_score(resume_text or "")

    # 加权：教育程度、专业关键词
    edu_skill_boost, edu_growth_boost = _education_boost(resume_text or "")
    domain_boost = _domain_boost(resume_tokens, job_tokens)
    skill_score = _normalize_score(skill_score + edu_skill_boost + domain_boost, 0, 100)
    growth_score = _normalize_score(growth_score + edu_growth_boost, 0, 100)

    # 经验分额外考虑教育背景（硕博经历通常伴随科研经验）
    exp_score = _normalize_score(exp_score + edu_skill_boost * 0.2, 0, 100)

    # 使用与AI评分一致的权重（强调岗位匹配度）
    total = (
        skill_score * 0.30  # 技能匹配度：30%
        + exp_score * 0.30  # 经验相关性：30%（岗位匹配度的关键）
        + growth_score * 0.20  # 成长潜力：20%
        + stability_score * 0.20  # 稳定性：20%
    )
    total = round(total, 1)

    evidence = _collect_evidence(resume_text or "", job_tokens)
    short_eval = f"[启发式] {_short_eval(total, skill_score, exp_score, growth_score)}"

    return {
        "总分": total,
        "维度得分": {
            "技能匹配度": round(skill_score, 1),
            "经验相关性": round(exp_score, 1),
            "成长潜力": round(growth_score, 1),
            "稳定性": round(stability_score, 1),
        },
        "证据": [evidence] if evidence else [],
        "简评": short_eval,
        "short_eval": short_eval,
    }


def _normalize_ai_scores(data: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    将大模型返回的 0-30 / 0-20 分制，统一映射到 0-100。
    返回 (规范化后的 data, 是否所有维度都是 0)。
    """
    if not isinstance(data, dict):
        raise ValueError("AI 返回值不是 JSON 对象")

    raw_dims = data.get("维度得分")
    if not isinstance(raw_dims, dict):
        raise ValueError("AI 返回值缺少 `维度得分` 字段")

    normalized_dims: Dict[str, float] = {}
    all_zero = True

    total_score = 0.0
    for key, meta in DIME_META.items():
        if key not in raw_dims:
            raise ValueError(f"AI 返回值缺少 `{key}` 分数")
        raw_value = raw_dims[key]
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            raise ValueError(f"{key} 分数不是数字：{raw_value!r}")

        if value > 0:
            all_zero = False

        max_value = meta["max"]
        normalized_value = _normalize_score(value / max_value * 100.0, 0.0, 100.0)
        normalized_dims[key] = round(normalized_value, 1)
        total_score += normalized_value * meta["weight"]

    data["维度得分"] = normalized_dims
    data["总分"] = round(_normalize_score(total_score, 0.0, 100.0), 1)
    return data, all_zero


def _heuristic_match_resumes_df(
    jd_text: str,
    resumes_df: pd.DataFrame,
    job_title: str | None = None,
) -> pd.DataFrame:
    """
    纯启发式的匹配算法，供 AI 打分失败时 fallback 使用，也可在调试阶段单独调用。
    """

    if resumes_df is None or resumes_df.empty:
        raise ValueError("resumes_df 为空，无法匹配")

    jd_clean = strip_competition_terms(jd_text or "", job_title or "")
    job_tokens = _top_keywords(_tokenize(jd_clean))

    scored_rows = []
    for _, row in resumes_df.iterrows():
        resume_text = str(row.get("resume_text", "") or "")
        tokens = set(_tokenize(resume_text))
        text_len = int(row.get("text_len") or len(resume_text))

        skill_score = _keyword_overlap_score(tokens, job_tokens)
        exp_score = _length_score(text_len)
        growth_score = _growth_score(resume_text)
        stability_score = _stability_score(resume_text)

        # 使用与AI评分一致的权重（强调岗位匹配度）
        total = (
            skill_score * 0.30  # 技能匹配度：30%
            + exp_score * 0.30  # 经验相关性：30%（岗位匹配度的关键）
            + growth_score * 0.20  # 成长潜力：20%
            + stability_score * 0.20  # 稳定性：20%
        )
        total = round(total, 1)

        evidence = _collect_evidence(resume_text, job_tokens)
        if evidence:
            evidence, _ = sanitize_for_job(job_title or "", evidence, evidence)

        short_eval = _short_eval(total, skill_score, exp_score, growth_score)

        enriched = row.to_dict()
        enriched.update(
            {
                "技能匹配度": round(skill_score, 1),
                "经验相关性": round(exp_score, 1),
                "成长潜力": round(growth_score, 1),
                "稳定性": round(stability_score, 1),
                "总分": total,
                "short_eval": short_eval,
                "证据": evidence,
            }
        )
        scored_rows.append(enriched)

    result = pd.DataFrame(scored_rows)
    result.sort_values(by="总分", ascending=False, inplace=True, ignore_index=True)
    return result

# 在导入其他模块之前，先设置 stdout 编码保护
try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
        # 包装 stdout 以处理编码错误
        if not hasattr(sys.stdout, '_original_write'):
            _original_stdout_write = sys.stdout.write
            def _safe_stdout_write(s):
                try:
                    _original_stdout_write(s)
                except (UnicodeEncodeError, UnicodeError):
                    # 尝试用 UTF-8 编码并替换无法编码的字符
                    try:
                        safe_s = s.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        _original_stdout_write(safe_s)
                    except Exception:
                        pass  # 如果还是失败，就忽略
            sys.stdout.write = _safe_stdout_write
            sys.stdout._original_write = _original_stdout_write
except Exception:
    pass  # 如果设置失败，继续执行

from backend.services.ai_client import get_client_and_cfg, chat_completion
from backend.services.competency_utils import determine_competency_strategy
from backend.utils.sanitize import sanitize_ai_output, SYSTEM_PROMPT
from backend.services.text_rules import sanitize_for_job, infer_job_family


def _safe_str(obj):
    """安全地将对象转换为字符串，处理编码错误"""
    if obj is None:
        return ""
    try:
        # 如果已经是字符串，直接返回
        if isinstance(obj, str):
            return obj
        # 尝试正常转换
        return str(obj)
    except (UnicodeEncodeError, UnicodeError):
        # 如果转换失败，使用安全的编码方式
        try:
            if isinstance(obj, str):
                return obj.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            else:
                # 先转换为字符串，再编码
                s = str(obj)
                return s.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        except Exception:
            # 如果还是失败，返回空字符串
            return ""


def _safe_join(items, separator="；"):
    """安全地连接字符串列表，处理编码错误"""
    try:
        return separator.join(_safe_str(item) for item in items if item)
    except (UnicodeEncodeError, UnicodeError):
        # 如果连接时出错，尝试逐个安全转换
        safe_items = []
        for item in items:
            if item:
                try:
                    safe_items.append(_safe_str(item))
                except Exception:
                    continue
        return separator.join(safe_items) if safe_items else ""


def _safe_print(*args, **kwargs):
    """安全的 print 函数，处理 Windows GBK 编码错误"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # 如果遇到编码错误，使用 errors='replace' 或 'ignore' 处理
        try:
            # 尝试将输出编码为 UTF-8
            if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
                # 临时设置 stdout 编码
                old_stdout = sys.stdout
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
                try:
                    print(*args, **kwargs)
                finally:
                    sys.stdout = old_stdout
            else:
                # 直接使用 replace 模式
                safe_args = []
                for arg in args:
                    if isinstance(arg, str):
                        safe_args.append(arg.encode('utf-8', errors='replace').decode('utf-8', errors='replace'))
                    else:
                        safe_args.append(str(arg).encode('utf-8', errors='replace').decode('utf-8', errors='replace'))
                print(*safe_args, **kwargs)
        except Exception:
            # 如果还是失败，就忽略这个 print
            pass


def _get_model(cfg: Any) -> str:
    if hasattr(cfg, "model"):
        return cfg.model
    if isinstance(cfg, dict):
        return cfg.get("model", "gpt-4o-mini")
    return "gpt-4o-mini"


def _get_temperature(cfg: Any) -> float:
    if hasattr(cfg, "temperature"):
        return float(getattr(cfg, "temperature"))
    if isinstance(cfg, dict):
        return float(cfg.get("temperature", 0.6))
    return 0.6


SHORT_EVAL_PROMPT = """
你是一名专业的招聘HR，请基于候选人的真实简历内容和岗位JD，生成结构化的评价。

【岗位JD】
{jd_text}

【候选人简历】
{resume_text}

**生成逻辑**：
- 优势 = 简历中符合 JD 要求的点（列出2-3条）
- 劣势 = 简历中未体现但 JD 要求的点（列出1-2条，如无则写"无明显劣势"）
- 匹配度 = 对 JD 的关键要求、经验相关度、岗位动作匹配度进行综合判断（高/中/低）

**输出格式（严格按此结构，不可变更）**：

【优势】
1. [第一条优势，基于简历真实内容]
2. [第二条优势，基于简历真实内容]

【劣势】
1. [第一条劣势，JD要求但简历未体现]
2. [第二条劣势，如无则写"无明显劣势"]

【匹配度】
[高/中/低] [一句话解释原因，基于优势劣势分析]

**要求**：
- 必须基于简历和JD的真实内容，禁止捏造
- 优势必须对应JD要求，劣势必须对应JD要求但简历未体现
- 匹配度判断必须基于优势劣势的综合分析
- 文风专业、简洁，不堆砌形容词
- 适配所有岗位类型（销售、市场、运营、行政、技术、教师等）
"""


def _prepare_resume_text(file_text: str) -> str:
    """
    新逻辑：确保完整简历不被 LLM 截断。
    将全文强制分成 2500~3000 字的片段，模型会按顺序阅读。
    """
    text = file_text.strip()
    if not text:
        return text
    
    size = 2800
    chunks = []
    for i in range(0, len(text), size):
        part = text[i:i+size]
        chunks.append(f"【Resume Part {len(chunks)+1}】\n{part}")
    
    return "\n\n".join(chunks)


def _generate_short_eval(client, cfg, resume_text: str, jd_text: str, job_title: str) -> str:
    """
    生成候选人的简短评价（short_eval）
    包含优势、劣势和岗位匹配评价
    """
    cleaned_text = (resume_text or "").strip()
    if not cleaned_text:
        return "简历解析失败，请检查文件格式"

    try:
        # 使用分段逻辑，确保完整传入
        prepared_resume = _prepare_resume_text(cleaned_text)
        prepared_jd = jd_text[:2000] if len(jd_text) > 2000 else jd_text  # JD不需要分段，但限制长度
        prompt = SHORT_EVAL_PROMPT.format(resume_text=prepared_resume, jd_text=prepared_jd)
        
        res = chat_completion(
            client,
            cfg,
            messages=[
                {"role": "system", "content": "你是一名专业的招聘HR，擅长结构化分析候选人简历与岗位的匹配度，输出格式必须严格遵循要求。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=400,  # 增加token数量以支持结构化输出
        )
        content = res["choices"][0]["message"]["content"].strip()
        
        # 确保内容不为空，并验证格式
        if not content or not content.strip():
            content = "【优势】\n1. 无明显优势\n\n【劣势】\n1. 无明显劣势\n\n【匹配度】\n低 简历信息不足，无法准确评估"
        else:
            # 验证格式是否包含必要的结构标记
            if "【优势】" not in content or "【劣势】" not in content or "【匹配度】" not in content:
                # 如果格式不对，尝试修复或使用默认格式
                content = "【优势】\n1. 无明显优势\n\n【劣势】\n1. 无明显劣势\n\n【匹配度】\n低 简历信息不足，无法准确评估"
        
        return content
    except Exception as err:
        # API 调用失败时，返回错误信息
        error_msg = f"AI评价生成失败：{str(err)[:30]}"
        return f"【优势】\n1. 无明显优势\n\n【劣势】\n1. 无明显劣势\n\n【匹配度】\n低 {error_msg}"


def ai_score_one(client, cfg, jd_text: str, resume_text: str, job_title: str = "") -> Dict[str, Any]:
    """综合启发式匹配和智能诊断，输出统一结构。"""
    safe_resume_text = _safe_str(resume_text or "")
    jd_clean = (jd_text or "").strip()
    job_title_clean = (job_title or "").strip()

    missing_required = not jd_clean or not safe_resume_text.strip() or not job_title_clean

    if missing_required:
        heuristic_scores = {
            "总分": 0,
            "维度得分": {
                "技能匹配度": 0,
                "经验相关性": 0,
                "成长潜力": 0,
                "稳定性": 0,
            },
        }
        insights = FALLBACK_RESPONSE.copy()
    else:
        heuristic_scores = _heuristic_score_from_text(jd_text, safe_resume_text, job_title_clean)
        insights = generate_ai_insights(job_title_clean, safe_resume_text)

    data = dict(heuristic_scores)
    data["ability_model"] = insights.get("ability_model", {})

    def _merge_scores():
        scores = insights.get("scores") or {}
        dim = data.get("维度得分", {})
        data["总分"] = float(scores.get("total_score", data.get("总分", 0)))
        data["维度得分"] = {
            "技能匹配度": float(scores.get("skill_match", dim.get("技能匹配度", 0))),
            "经验相关性": float(scores.get("experience_match", dim.get("经验相关性", 0))),
            "成长潜力": float(scores.get("growth_potential", dim.get("成长潜力", 0))),
            "稳定性": float(scores.get("stability", dim.get("稳定性", 0))),
        }
        data["score_explain"] = scores.get("score_explain", "")

    def _apply_short_eval():
        short_eval_struct = insights.get("short_eval") or {}
        data["short_eval_struct"] = short_eval_struct
        data["short_eval"] = _format_short_eval_struct(short_eval_struct)

    def _apply_evidence():
        evidence_struct = insights.get("evidence") or {}
        data["reasoning_chain"] = evidence_struct
        formatted = _format_reasoning_text(evidence_struct)
        if not formatted:
            formatted = (
                "【优势推理链】\n1. 暂无有效证据\n\n"
                "【劣势推理链】\n1. 简历未体现相关内容"
            )
        data["证据"] = formatted

    def _apply_ui():
        ui_struct = insights.get("ui") or {"row_display": "", "highlights": []}
        data["summary_for_ui"] = ui_struct

    data["resume_mini"] = insights.get("resume_text", "")

    if not insights.get("fallback") and not missing_required:
        _merge_scores()
    else:
        data["总分"] = 0
        data["维度得分"] = {"技能匹配度": 0, "经验相关性": 0, "成长潜力": 0, "稳定性": 0}
        data["score_explain"] = ""

    _apply_short_eval()
    _apply_evidence()
    _apply_ui()

    return data



def ai_match_resumes_df(jd_text: str, resumes_df: pd.DataFrame, job_title: str = "") -> pd.DataFrame:
    """
    对外统一入口：基于 AI 打分，失败时自动回退到启发式评分，避免“全 0 分”。
    """
    # 在函数开始时设置 stdout 编码，避免后续编码错误
    try:
        import sys
        import io
        if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
            if not hasattr(sys.stdout, '_original_write'):
                sys.stdout._original_write = sys.stdout.write

                def safe_write(s):
                    try:
                        sys.stdout._original_write(s)
                    except UnicodeEncodeError:
                        safe_s = s.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        sys.stdout._original_write(safe_s)

                sys.stdout.write = safe_write
    except Exception:
        pass

    try:
        client, cfg = get_client_and_cfg()
        ai_available = True
    except Exception as err:
        ai_available = False
        _safe_print(f"[AI matcher] 获取 AI 客户端失败，将使用启发式评分：{err}")
        return _heuristic_match_resumes_df(jd_text, resumes_df, job_title)

    if not job_title:
        job_title = "销售顾问"

    try:
        job_family = infer_job_family(job_title)
        strategy_category, _ = determine_competency_strategy(job_title)
    except Exception:
        job_family = "generic"
        strategy_category = "通用维度"

    if strategy_category and strategy_category != "通用维度":
        effective_job_label = strategy_category
    elif job_family and job_family != "general":
        effective_job_label = job_family
    else:
        effective_job_label = job_title

    if "resume_text" not in resumes_df.columns:
        resumes_df = resumes_df.copy()
        fallback_candidates = ["text", "full_text", "content", "parsed_text"]
        fallback = next((col for col in fallback_candidates if col in resumes_df.columns), None)
        if fallback:
            resumes_df["resume_text"] = resumes_df[fallback].fillna("")
        else:
            resumes_df["resume_text"] = ""

    rows = []
    for idx in resumes_df.index:
        resume_text = _safe_str(resumes_df.loc[idx, "resume_text"] or "")
        file_name = resumes_df.loc[idx, "file"] if "file" in resumes_df.columns else ""

        if ai_available:
            try:
                result = ai_score_one(client, cfg, jd_text, resume_text, effective_job_label)
            except Exception as e:
                # 如果单条 AI 调用失败，回退到启发式评分
                result = _heuristic_score_from_text(jd_text, resume_text, effective_job_label)
                result["short_eval"] = result.get("short_eval") or f"AI智能评价失败：{_safe_str(e)}"
        else:
            result = _heuristic_score_from_text(jd_text, resume_text, effective_job_label)

        # 构建行数据
        row_data = {
            "candidate_id": resumes_df.loc[idx, "candidate_id"] if "candidate_id" in resumes_df.columns else None,
            "file": file_name,
            "name": resumes_df.loc[idx, "name"] if "name" in resumes_df.columns else "",
            "email": resumes_df.loc[idx, "email"] if "email" in resumes_df.columns else "",
            "phone": resumes_df.loc[idx, "phone"] if "phone" in resumes_df.columns else "",
            "resume_text": resume_text,
            "resume_mini": result.get("resume_mini", ""),
            "总分": result.get("总分", 0),
            "技能匹配度": result.get("维度得分", {}).get("技能匹配度", 0),
            "经验相关性": result.get("维度得分", {}).get("经验相关性", 0),
            "成长潜力": result.get("维度得分", {}).get("成长潜力", 0),
            "稳定性": result.get("维度得分", {}).get("稳定性", 0),
            "short_eval": result.get("short_eval") or result.get("简评", ""),
            "short_eval_struct": json.dumps(result.get("short_eval_struct", {}), ensure_ascii=False),
            "ability_model": json.dumps(result.get("ability_model", {}), ensure_ascii=False),
            "reasoning_chain": json.dumps(result.get("reasoning_chain", {}), ensure_ascii=False),
            "证据": result.get("证据") if isinstance(result.get("证据"), str) else (
                "\n".join(result.get("证据") or []) if isinstance(result.get("证据"), list) else "【优势证据】\n1. 优势 → 简历未体现相关内容\n\n【劣势证据】\n1. 劣势 → 简历未体现相关内容"
            ),
            "text_len": resumes_df.loc[idx, "text_len"] if "text_len" in resumes_df.columns else len(resume_text),
        }
        
        # 添加新格式的字段（如果存在）
        if "score_explain" in result:
            row_data["score_explain"] = result["score_explain"]
        
        summary_ui = result.get("summary_for_ui") or {}
        if isinstance(summary_ui, dict):
            row_display = summary_ui.get("row_display", "")
            highlight_list = summary_ui.get("highlights", [])
        else:
            row_display = ""
            highlight_list = []

        if not row_display:
            row_display = (
                result.get("short_eval_struct", {}).get("match_reason", "").strip()
                or "匹配结果待人工复核"
            )[:18]

        if not isinstance(highlight_list, list) or not highlight_list:
            strengths = result.get("short_eval_struct", {}).get("core_strengths", [])
            if isinstance(strengths, list):
                highlight_list = [s[:4] for s in strengths[:2]]
            else:
                highlight_list = []

        row_data["row_display"] = row_display
        row_data["highlights"] = "｜".join([h for h in highlight_list if h])
        
        rows.append(row_data)

    df = pd.DataFrame(rows)

    if "简评" in df.columns and "short_eval" not in df.columns:
        df["short_eval"] = df.pop("简评")

    return df



