import json
from typing import Any, Dict

from backend.services.ai_client import get_client_and_cfg, chat_completion


def _call_chat(messages, temperature: float = 0.6) -> str:
    client, cfg = get_client_and_cfg()
    model = getattr(cfg, "model", None) or (cfg.get("model") if isinstance(cfg, dict) else None) or "gpt-4o-mini"
    temp = temperature if temperature is not None else getattr(cfg, "temperature", 0.6)

    res = chat_completion(
        client,
        cfg,
        messages=messages,
        temperature=temp,
    )
    return res.choices[0].message.content.strip()


def generate_ai_summary(row: Dict[str, Any]) -> str:
    """AI 自动提炼候选亮点"""
    text = json.dumps(row, ensure_ascii=False)
    prompt = f"请根据以下候选人信息，总结3个亮点，用简短中文短句表示（使用编号）：\n{text}"
    return _call_chat(
        messages=[
            {"role": "system", "content": "你是一名熟悉教育行业的招聘专家。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
    )


def generate_ai_email(name: str, highlights: str, position: str, score: Any, ics_path: str) -> str:
    """AI 自动生成面试邀约邮件内容"""
    prompt = f"""
你是教育公司HR。请为候选人生成一封简洁温暖的面试邀约邮件，要求包含：
1️⃣ 候选人姓名（如{name}）；
2️⃣ 职位名称（如{position}）；
3️⃣ 匹配亮点（如下：{highlights}）；
4️⃣ 附件说明（{ics_path}）；
5️⃣ 总分（{score}）。
"""
    return _call_chat(
        messages=[
            {"role": "system", "content": "你是一名擅长写邀约邮件的HR，语气友好、真诚、专业。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )

