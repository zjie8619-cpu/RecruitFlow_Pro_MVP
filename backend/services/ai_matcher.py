"""
Lightweight heuristic matcher used when the heavy AI pipeline is unavailable.
It scores resumes against a JD text and returns a dataframe with scoring columns
expected by the Streamlit UI.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import pandas as pd

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

    skill_score = _keyword_overlap_score(resume_tokens, job_tokens)
    exp_score = _length_score(text_len)
    growth_score = _growth_score(resume_text or "")
    stability_score = _stability_score(resume_text or "")

    # 加权：教育程度、专业关键词
    edu_skill_boost, edu_growth_boost = _education_boost(resume_text or "")
    domain_boost = _domain_boost(resume_tokens, job_tokens)
    skill_score = _normalize_score(skill_score + edu_skill_boost + domain_boost, 0, 100)
    growth_score = _normalize_score(growth_score + edu_growth_boost, 0, 100)

    # 经验分额外考虑教育背景（硕博经历通常伴随科研经验）
    exp_score = _normalize_score(exp_score + edu_skill_boost * 0.4, 0, 100)

    total = (
        skill_score * 0.45
        + exp_score * 0.25
        + growth_score * 0.2
        + stability_score * 0.1
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

        total = (
            skill_score * 0.4
            + exp_score * 0.3
            + growth_score * 0.2
            + stability_score * 0.1
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
你是一名专业的教育行业 HR，请基于候选人的真实简历内容，用一句中文生成 20~40 字的高度概括评价。

要求：
- 必须从简历内容中提炼，禁止使用模板句
- 必须准确反映候选人的专业背景、经验特点或亮点
- 如果是教师/教练岗位，严禁出现"销售、开发客户、拉新、转化、邀约、电销"等与教育无关的词
- 允许使用"沟通、负责、授课、家长、学生、教学"等教育行业正常词汇
- 不得捏造不存在的经历
- 不得输出"简历信息不足"或类似话术
- 若文本为空，则直接返回："简历解析失败，请检查文件格式"

【简历内容】
{resume_text}
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


def _generate_short_eval(client, cfg, resume_text: str, job_title: str) -> str:
    """
    生成候选人的简短评价（short_eval）
    确保返回真实的 AI 评价，而不是异常提示
    """
    cleaned_text = (resume_text or "").strip()
    if not cleaned_text:
        return "简历解析失败，请检查文件格式"

    try:
        # 使用分段逻辑，确保完整传入（简评也需要看到完整简历）
        prepared_resume = _prepare_resume_text(cleaned_text)
        prompt = SHORT_EVAL_PROMPT.format(resume_text=prepared_resume)
        
        res = chat_completion(
            client,
            cfg,
            messages=[
                {"role": "system", "content": "你是一名专业的教育行业 HR，擅长从简历中提炼候选人亮点。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=150,
        )
        content = res["choices"][0]["message"]["content"].strip()
        
        # 轻度清洗：只去除明显的销售词汇，保留原始评价
        if content:
            # 对于教育行业岗位，只去除明显不相关的词汇
            education_keywords = ["课程", "顾问", "教师", "教练", "招生", "学管"]
            is_education = any(k in job_title for k in education_keywords)
            
            if is_education:
                # 教育行业：只去除销售词汇，保留其他所有内容
                sales_words = ["开发客户", "拉新", "转化", "邀约", "电销"]
                for word in sales_words:
                    content = content.replace(word, "")
                content = re.sub(r"\s+", " ", content).strip()
            else:
                # 非教育行业：轻度清洗，但保留原始内容
                content = sanitize_ai_output(content, job_title)
                # 如果被替换为异常提示，尝试使用原始内容
                if "存在异常" in content:
                    # 回退到原始内容，只做最基本的清理
                    content = res["choices"][0]["message"]["content"].strip()
        
        # 确保 short_eval 永不被清空或被替换为异常提示
        if not content or not content.strip() or "存在异常" in content:
            # 如果内容为空或被替换为异常，使用原始 AI 返回
            original_content = res["choices"][0]["message"]["content"].strip()
            if original_content and len(original_content) > 10:
                content = original_content[:100]  # 使用原始内容的前100字符
            else:
                # 最后的兜底：生成一个通用的评价
                content = "该候选人具备相关工作经验，请结合简历进一步评估。"
        
        return content
    except Exception as err:
        # API 调用失败时，返回错误信息而不是异常提示
        error_msg = f"AI评价生成失败：{str(err)[:50]}"
        return error_msg


def ai_score_one(client, cfg, jd_text: str, resume_text: str, job_title: str = "") -> Dict[str, Any]:
    """
    对单个候选人进行 AI 评分
    所有字符串处理都使用安全的编码方式
    """
    try:
        # 使用统一的防幻觉系统提示词
        # 步骤1：强制分段，确保完整传入
        prepared_resume = _prepare_resume_text(resume_text)

        prompt = f"""
你是资深招聘面试官。请基于下面信息对候选人进行匹配评分，返回中文 JSON，且只返回 JSON：

【岗位 JD】
{jd_text}

【候选人简历】
{prepared_resume}

评分口径（总分 100）：
- 技能匹配度（30）
- 经验相关性（30）
- 成长潜力（20）
- 稳定性与岗位适配性（20）

请根据你能识别到的信息进行评分。
某些字段缺失（如项目/教育/技能）属于正常情况，不要返回"信息不足"。
如果某部分缺失，请在输出中注明：
"此部分信息缺失，已按已有信息进行估算。"

永远不要返回"信息不足"。

输出严格 JSON：
{{
  "总分": <0-100的整数>,
  "维度得分": {{
    "技能匹配度": <0-30>,
    "经验相关性": <0-30>,
    "成长潜力": <0-20>,
    "稳定性": <0-20>
  }},
  "证据": ["使用简历中的引用语句或要点，2-4条"],
  "简评": "一句中文总结"
}}
只返回 JSON 对象，不能包含任何解释。
"""
        res = chat_completion(
            client,
            cfg,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=_get_temperature(cfg),
        )
        
        # 步骤3：JSON 输出容错补丁
        raw_content = res["choices"][0]["message"]["content"]
        try:
            data = _parse_ai_json(raw_content)
        except Exception as e:
            fallback = _heuristic_score_from_text(jd_text, resume_text, job_title)
            fallback["解析错误"] = _safe_str(e)[:100]
            return fallback

        try:
            data, dimensions_all_zero = _normalize_ai_scores(data)
        except Exception as e:
            fallback = _heuristic_score_from_text(jd_text, resume_text, job_title)
            fallback["解析错误"] = _safe_str(e)[:100]
            return fallback
        
        # 🚫 防幻觉过滤：清理"证据"和"简评"（优化版，避免过度清洗）
        if job_title:
            evidence_list = data.get("证据", [])
        
        # 判断是否为教育行业岗位
        education_keywords = ["课程", "顾问", "教师", "教练", "招生", "学管", "班主任", "教研"]
        is_education = any(k in job_title for k in education_keywords)
        
        if is_education:
            # 教育行业岗位：只去除明显的销售词汇，保留所有其他内容
            cleaned_evidence = []
            for ev in evidence_list:
                if ev and ev.strip():
                    # 只去除销售相关词汇
                    cleaned = ev
                    for word in ["开发客户", "拉新", "转化", "邀约", "电销"]:
                        cleaned = cleaned.replace(word, "")
                    cleaned = re.sub(r"\s+", " ", cleaned).strip()
                    if cleaned:
                        cleaned_evidence.append(cleaned)
            
            # 简评也做同样处理
            summary_text = data.get("简评", "")
            if summary_text:
                for word in ["开发客户", "拉新", "转化", "邀约", "电销"]:
                    summary_text = summary_text.replace(word, "")
                summary_text = re.sub(r"\s+", " ", summary_text).strip()
            
            data["证据"] = cleaned_evidence
            data["简评"] = summary_text
        else:
            # 非教育岗位：轻度清洗，但保留原始内容
            cleaned_evidence = []
            for ev in evidence_list:
                if ev and ev.strip():
                    cleaned = sanitize_ai_output(ev, job_title)
                    # 如果被替换为异常提示，保留原始证据
                    if "存在异常" in cleaned:
                        cleaned = ev  # 回退到原始证据
                    if cleaned and cleaned.strip():
                        cleaned_evidence.append(cleaned)
            
            summary_text = data.get("简评", "")
            if summary_text:
                cleaned_summary = sanitize_ai_output(summary_text, job_title)
                # 如果被替换为异常提示，保留原始简评
                if "存在异常" in cleaned_summary:
                    cleaned_summary = summary_text
                summary_text = cleaned_summary
            
            data["证据"] = cleaned_evidence
            data["简评"] = summary_text

        applied_zero_fallback = False
        resume_length = len((resume_text or "").strip())
        if dimensions_all_zero and resume_length > 150:
            heuristic_scores = _heuristic_score_from_text(jd_text, resume_text, job_title)
            data["维度得分"] = heuristic_scores["维度得分"]
            data["总分"] = heuristic_scores["总分"]
            if not data.get("证据"):
                data["证据"] = heuristic_scores["证据"]
            if not data.get("简评"):
                data["简评"] = heuristic_scores["简评"]
            applied_zero_fallback = True

        try:
            ai_summary = _generate_short_eval(client, cfg, resume_text, job_title)
            # 确保不是异常提示（使用安全的字符串检查）
            try:
                ai_summary_str = _safe_str(ai_summary)
                if ai_summary_str and "存在异常" in ai_summary_str:
                    # 如果被替换为异常提示，使用简评作为替代
                    ai_summary = data.get("简评", "该候选人具备相关工作经验，请结合简历进一步评估。")
            except (UnicodeEncodeError, UnicodeError):
                # 如果检查时出现编码错误，直接使用简评
                ai_summary = data.get("简评", "该候选人具备相关工作经验，请结合简历进一步评估。")
        except Exception as err:
            # API 调用失败时，使用简评或生成通用评价
            try:
                err_str = _safe_str(err)[:50]
                ai_summary = data.get("简评", f"AI评价生成失败：{err_str}")
                data["短评_error"] = err_str
            except (UnicodeEncodeError, UnicodeError):
                ai_summary = data.get("简评", "该候选人具备相关工作经验，请结合简历进一步评估。")
                data["短评_error"] = "编码错误"
        try:
            if applied_zero_fallback:
                data["short_eval"] = f"[AI 初始评分为 0，已回退启发式] {ai_summary}"
            else:
                data["short_eval"] = ai_summary
        except (UnicodeEncodeError, UnicodeError):
            # 如果赋值时出现编码错误，使用安全的默认值
            data["short_eval"] = "该候选人具备相关工作经验，请结合简历进一步评估。"
        
        # 🔧 最终统一替换：确保所有字段都不包含异常提示
        fallback_text = "该候选人具备相关工作经验，请结合简历进一步评估。"
        
        # 替换证据中的异常提示（使用安全的字符串处理）
        try:
            evidence_list = data.get("证据", [])
            cleaned_evidence = []
            for ev in evidence_list:
                try:
                    # 安全地转换和检查字符串
                    ev_str = _safe_str(ev)
                    # 安全地检查字符串，避免编码错误
                    if ev_str:
                        try:
                            if "存在异常" not in ev_str:
                                cleaned_evidence.append(ev)
                        except (UnicodeEncodeError, UnicodeError):
                            # 如果检查时出错，跳过这个证据
                            continue
                except (UnicodeEncodeError, UnicodeError, Exception):
                    # 如果处理单个证据时出错，跳过它
                    continue
            if not cleaned_evidence and evidence_list:
                # 如果所有证据都被过滤，至少保留一条通用描述
                cleaned_evidence = ["候选人具备相关工作经验。"]
            data["证据"] = cleaned_evidence
        except (UnicodeEncodeError, UnicodeError, Exception) as e:
            # 如果处理证据时出错，使用默认值
            data["证据"] = ["候选人具备相关工作经验。"]
        
        # 替换简评中的异常提示（使用安全的字符串处理）
        try:
            if "简评" in data:
                summary = data["简评"]
                if summary:
                    try:
                        # 安全地转换字符串
                        summary_str = _safe_str(summary)
                        # 安全地检查字符串
                        try:
                            if summary_str and "存在异常" in summary_str:
                                data["简评"] = fallback_text
                        except (UnicodeEncodeError, UnicodeError):
                            data["简评"] = fallback_text
                    except (UnicodeEncodeError, UnicodeError):
                        data["简评"] = fallback_text
        except (UnicodeEncodeError, UnicodeError, Exception):
            if "简评" in data:
                data["简评"] = fallback_text
        
        # 替换 short_eval 中的异常提示（使用安全的字符串处理）
        try:
            if "short_eval" in data:
                short_eval = data["short_eval"]
                if short_eval:
                    try:
                        # 安全地转换字符串
                        short_eval_str = _safe_str(short_eval)
                        # 安全地检查字符串
                        try:
                            if short_eval_str and "存在异常" in short_eval_str:
                                data["short_eval"] = fallback_text
                        except (UnicodeEncodeError, UnicodeError):
                            data["short_eval"] = fallback_text
                    except (UnicodeEncodeError, UnicodeError):
                        data["short_eval"] = fallback_text
        except (UnicodeEncodeError, UnicodeError, Exception):
            if "short_eval" in data:
                data["short_eval"] = fallback_text
        
        return data
    except (UnicodeEncodeError, UnicodeError) as e:
        # 如果整个函数执行过程中出现编码错误，返回安全的默认值
        return {
            "总分": 0,
            "维度得分": {"技能匹配度": 0, "经验相关性": 0, "成长潜力": 0, "稳定性": 0},
            "证据": ["候选人具备相关工作经验。"],
            "简评": "该候选人具备相关工作经验，请结合简历进一步评估。",
            "short_eval": "该候选人具备相关工作经验，请结合简历进一步评估。",
            "编码错误": "处理过程中出现编码问题，已使用默认值"
        }
    except Exception as e:
        # 其他异常：使用启发式评分兜底，而不是全 0 分
        fallback = _heuristic_score_from_text(jd_text, resume_text, job_title)
        fallback["处理错误"] = _safe_str(e)[:100]
        return fallback


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

        rows.append(
            {
                "candidate_id": resumes_df.loc[idx, "candidate_id"] if "candidate_id" in resumes_df.columns else None,
                "file": file_name,
                "name": resumes_df.loc[idx, "name"] if "name" in resumes_df.columns else "",
                "email": resumes_df.loc[idx, "email"] if "email" in resumes_df.columns else "",
                "phone": resumes_df.loc[idx, "phone"] if "phone" in resumes_df.columns else "",
                "resume_text": resume_text,
                "总分": result.get("总分", 0),
                "技能匹配度": result.get("维度得分", {}).get("技能匹配度", 0),
                "经验相关性": result.get("维度得分", {}).get("经验相关性", 0),
                "成长潜力": result.get("维度得分", {}).get("成长潜力", 0),
                "稳定性": result.get("维度得分", {}).get("稳定性", 0),
                "short_eval": result.get("short_eval") or result.get("简评", ""),
                "证据": _safe_join(result.get("证据") or [], "；"),
                "text_len": resumes_df.loc[idx, "text_len"] if "text_len" in resumes_df.columns else len(resume_text),
            }
        )

    df = pd.DataFrame(rows)

    if "简评" in df.columns and "short_eval" not in df.columns:
        df["short_eval"] = df.pop("简评")

    return df



