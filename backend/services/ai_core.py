from typing import Any, Dict

from backend.services.ai_client import get_client_and_cfg, chat_completion

SUMMARY_SYSTEM_PROMPT = (
    "你是一位资深招聘官，需要基于候选人信息生成 2-3 句亮点总结，"
    "语气专业、积极，适合放入面试邀约邮件。"
)

EMAIL_SYSTEM_PROMPT = (
    "你是一位专业 HR，请根据候选人信息撰写面试邀约邮件。"
    "邮件需友好、简洁，包含问候、岗位信息、亮点、面试安排以及礼貌结尾。"
)


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _join_evidence(evidence: Any) -> str:
    if isinstance(evidence, (list, tuple, set)):
        return "; ".join(str(item).strip() for item in evidence if item)
    if evidence:
        return str(evidence)
    return ""


def generate_ai_summary(candidate_dict: Dict[str, Any]) -> str:
    """基于候选人信息生成亮点总结。"""
    name = (
        _safe_text(candidate_dict.get("file"))
        or _safe_text(candidate_dict.get("name"), "候选人")
    )
    score = (
        candidate_dict.get("总分")
        or candidate_dict.get("score_total")
        or candidate_dict.get("score")
        or "未知"
    )
    short_eval = _safe_text(
        candidate_dict.get("short_eval") or candidate_dict.get("简评"), ""
    )
    evidence_text = _join_evidence(
        candidate_dict.get("证据") or candidate_dict.get("evidence")
    )
    skill_fit = candidate_dict.get("技能匹配度") or candidate_dict.get("skill_fit", 0)
    exp_relevance = (
        candidate_dict.get("经验相关性") or candidate_dict.get("exp_relevance", 0)
    )

    prompt = f"""候选人姓名: {name}
综合评分: {score}
AI 评价: {short_eval or '暂无'}
匹配证据: {evidence_text or '暂无'}
技能匹配度: {skill_fit}
经验相关性: {exp_relevance}

请用 2-3 句话输出候选人的亮点，突出其能力和岗位匹配度，字数不超过 120，并适合放入面试邀约邮件。"""

    try:
        client, cfg = get_client_and_cfg()
    except Exception:
        return short_eval or f"{name}在岗位匹配度方面表现积极，建议进一步沟通。"

    try:
        response = chat_completion(
            client,
            cfg,
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=220,
        )
        summary = (
            response["choices"][0]["message"]["content"]
            .replace("```", "")
            .strip()
        )
        if not summary or len(summary) < 10:
            raise ValueError("summary too short")
        return summary
    except Exception:
        fallback = short_eval or evidence_text
        if fallback:
            return f"{name}: {fallback[:100]}"
        return f"{name}在技能匹配度与经验方面表现良好，期待进一步沟通。"


def generate_ai_email(
    name: str,
    highlights: str,
    position: str,
    score: Any,
    ics_path: str = "",
) -> str:
    """生成面试邀约邮件。"""
    name = _safe_text(name, "候选人")
    highlights = _safe_text(highlights, "在匹配度和经验方面表现良好")
    position = _safe_text(position, "目标岗位")
    score_display = _safe_text(score, "N/A")
    ics_info = (
        "已附上日历邀请，请查收。"
        if ics_path and ics_path != "(附件生成失败)"
        else "如需调整时间可随时告知。"
    )

    prompt = f"""请根据以下信息生成一封中文面试邀约邮件:
- 候选人姓名: {name}
- 岗位名称: {position}
- 候选人亮点: {highlights}
- 综合评分: {score_display}
- 日历说明: {ics_info}

邮件要求:
1. 开头称呼候选人姓名并表示感谢。
2. 提及岗位名称、亮点和下一步面试安排(30-45分钟)。
3. 如果有日历附件提醒候选人确认，没有则给出时间协调说明。
4. 结束语礼貌，落款为 HR Team。
5. 不要添加额外标题，只输出邮件正文。"""

    try:
        client, cfg = get_client_and_cfg()
    except Exception:
        return _generate_template_email(name, highlights, position, score_display, ics_info)

    try:
        response = chat_completion(
            client,
            cfg,
            messages=[
                {"role": "system", "content": EMAIL_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            max_tokens=500,
        )
        email_body = (
            response["choices"][0]["message"]["content"]
            .replace("```", "")
            .strip()
        )
        if not email_body or len(email_body) < 50:
            raise ValueError("email too short")
        return email_body
    except Exception:
        return _generate_template_email(name, highlights, position, score_display, ics_info)


def _generate_template_email(
    name: str,
    highlights: str,
    position: str,
    score: Any,
    ics_note: str,
) -> str:
    """备用模板邮件。"""
    return (
        f"Hi {name},\n\n"
        f"感谢你对 {position} 岗位的关注，我们希望与您安排一次约 30-45 分钟的初步交流。\n\n"
        f"亮点摘要：{highlights}\n"
        f"综合评分：{score}\n"
        f"{ics_note}\n\n"
        "如需调整时间请随时告知，我们期待与您进一步沟通。\n\n"
        "HR Team"
    )