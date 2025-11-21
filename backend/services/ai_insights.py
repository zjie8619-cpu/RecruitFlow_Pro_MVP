import json
import textwrap
from typing import Dict, List, Any

from backend.services.ai_client import get_client_and_cfg, chat_completion


FALLBACK_RESPONSE = {
    "resume_text": "",
    "short_eval": {
        "core_strengths": [],
        "core_weaknesses": ["信息不足，无法进行岗位匹配分析"],
        "match_level": "无法评估",
        "match_reason": "缺少 JD 或简历内容",
    },
    "evidence": {
        "strengths_reasoning_chain": [],
        "weaknesses_reasoning_chain": [],
    },
    "ui": {
        "row_display": "",
        "highlights": [],
    },
    "scores": {
        "total_score": 0,
        "skill_match": 0,
        "experience_match": 0,
        "growth_potential": 0,
        "stability": 0,
        "score_explain": "",
    },
    "ability_model": {},
    "fallback": True,
}


ABILITY_RULES = [
    {
        "keywords": ["班主任", "学管", "教务"],
        "model": {
            "core_duties": ["学员管理", "家长沟通", "学习督导"],
            "core_actions": ["电话回访", "学习计划跟进", "社群运营"],
            "core_skills": ["沟通表达", "服务意识", "执行力"],
            "preferred_exp": ["教育/培训行业", "班主任/学管经验"],
            "risks": ["稳定性不足", "缺少家校沟通动作"],
            "talent_tags": ["家校沟通", "学习督导"],
        },
    },
    {
        "keywords": ["销售", "顾问", "BD", "商务"],
        "model": {
            "core_duties": ["客户拓展", "需求诊断", "成交转化"],
            "core_actions": ["邀约触达", "方案演示", "异议处理"],
            "core_skills": ["销售动作", "沟通谈判", "目标达成"],
            "preferred_exp": ["同业销售经验", "完整业绩证明"],
            "risks": ["缺少电销动作", "行业迁移成本高", "缺乏成交案例"],
            "talent_tags": ["邀约跟进", "成交转化"],
        },
    },
    {
        "keywords": ["运营", "策划", "活动"],
        "model": {
            "core_duties": ["活动策划", "数据复盘", "用户运营"],
            "core_actions": ["项目推进", "跨部门协作", "效果评估"],
            "core_skills": ["项目管理", "数据分析", "内容策划"],
            "preferred_exp": ["互联网运营经验", "项目落地案例"],
            "risks": ["缺少数据能力", "缺乏闭环复盘"],
            "talent_tags": ["活动策划", "数据复盘"],
        },
    },
]


def ability_model_generator(job_title: str) -> Dict[str, List[str]]:
    job_lower = (job_title or "").lower()
    for rule in ABILITY_RULES:
        if any(keyword.lower() in job_lower for keyword in rule["keywords"]):
            return rule["model"]
    # 通用模板
    base = job_title or "该岗位"
    return {
        "core_duties": [f"{base}关键职责一", f"{base}关键职责二"],
        "core_actions": [f"{base}常见动作一", f"{base}常见动作二"],
        "core_skills": ["沟通协作", "执行力", "学习能力"],
        "preferred_exp": [f"{base}相关经验", "跨团队协作经验"],
        "risks": ["缺少行业经验", "缺少核心动作复用"],
        "talent_tags": ["执行力", "学习力"],
    }


def _parse_llm_json(raw: str) -> Dict[str, Any]:
    if not raw:
        raise ValueError("empty content")
    candidates = [raw.strip()]
    if raw.strip().startswith("```"):
        stripped = raw.strip().strip("`")
        stripped = stripped.replace("json", "", 1).strip()
        candidates.append(stripped)
    start = raw.find("{")
    end = raw.rfind("}")
    if 0 <= start < end:
        candidates.append(raw[start : end + 1])
    for cand in candidates:
        try:
            return json.loads(cand)
        except Exception:
            continue
    raise ValueError("unable to parse ai insights json")


def _call_insight_llm(job_title: str, resume_text: str, ability_model: Dict[str, Any]) -> Dict[str, Any]:
    client, cfg = get_client_and_cfg()
    prompt = textwrap.dedent(
        f"""
        你是一名资深人才顾问，需要基于岗位名称与候选人简历，生成“岗位能力模型 + 简历诊断 + 推理链”。

        【岗位名称】
        {job_title}

        【岗位能力模型（可补充）】
        {json.dumps(ability_model, ensure_ascii=False, indent=2)}

        【候选人简历】
        {resume_text}

        请输出严格 JSON（字段名不可更改），并务必体现“岗位 → 动作 → 推理”的链式逻辑：
        {{
          "resume_text": "重写短版简历（150-180字）：第一行写“核心标签：A｜B｜C”，其后包含倒序关键经历（2段，每段2-3条动作）、核心能力、教育背景。禁止照搬原文。",
          "short_eval": {{
            "core_strengths": ["基于能力模型的优势（≤18字）", "…"],
            "core_weaknesses": ["基于能力模型的劣势（≤18字）", "…"],
            "match_level": "高/中/低",
            "match_reason": "一句话解释匹配逻辑（结合动作 + 风险）"
          }},
          "scores": {{
            "total_score": <0-100>,
            "skill_match": <0-30>,
            "experience_match": <0-30>,
            "growth_potential": <0-20>,
            "stability": <0-20>,
            "score_explain": "技能：xx；经验：xx；风险：xx"
          }},
          "evidence": {{
            "strengths_reasoning_chain": [
              {{
                "conclusion": "能力+动作导向的优势（如“邀约动作完整，促成转化”）",
                "detected_actions": "只写简历中出现的动作/行为（必须包含动词）",
                "resume_evidence": "引用原文，并补充 AI 解释，格式“原文：…｜解释：…”",
                "ai_reasoning": "三段式：岗位需要的动作 → 简历动作如何覆盖 → 为什么构成优势"
              }}
            ],
            "weaknesses_reasoning_chain": [
              {{
                "conclusion": "基于缺失动作的劣势（如“缺少异议处理闭环”）",
                "resume_gap": "明确缺了哪些动作，不能写“缺经验”",
                "compare_to_jd": "岗位模型为什么必须该动作（说明业务场景）",
                "ai_reasoning": "阐述风险：缺口→影响邀约/跟进/转化等指标→造成哪些结果"
              }}
            ]
          }},
          "ui": {{
            "row_display": "12-18字摘要，描述候选人匹配特点",
            "highlights": ["2个标签，每个≤4字，来源于岗位动作/能力模型"]
          }}
        }}
        仅返回 JSON。
        """
    )
    response = chat_completion(
        client,
        cfg,
        messages=[
            {"role": "system", "content": "你是一名能够输出结构化人才洞察的AI人才顾问。"},
            {"role": "user", "content": prompt},
        ],
        temperature=cfg.temperature,
        max_tokens=1500,
    )
    content = response["choices"][0]["message"]["content"]
    return _parse_llm_json(content)


def _ensure_list(data: Any) -> List[str]:
    if isinstance(data, list):
        return [str(item) for item in data]
    if isinstance(data, str):
        return [data]
    return []
def _sanitize_evidence(evidence: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(evidence, dict):
        return {"strengths_reasoning_chain": [], "weaknesses_reasoning_chain": []}

    def _filter_chain(chain, allowed):
        cleaned = []
        for item in chain:
            if not isinstance(item, dict):
                continue
            if not item.get("resume_gap") and not item.get("compare_to_jd"):
                cleaned_item = {k: v for k, v in item.items() if k in allowed}
            else:
                cleaned_item = item
            cleaned.append(cleaned_item)
        return cleaned

    strengths = _filter_chain(
        evidence.get("strengths_reasoning_chain") or [],
        {"conclusion", "detected_actions", "resume_evidence", "ai_reasoning"},
    )
    weaknesses = _filter_chain(
        evidence.get("weaknesses_reasoning_chain") or [],
        {"conclusion", "resume_gap", "compare_to_jd", "ai_reasoning"},
    )
    return {
        "strengths_reasoning_chain": strengths,
        "weaknesses_reasoning_chain": weaknesses,
    }


def _trim(text: str, limit: int) -> str:
    content = (text or "").strip()
    if len(content) <= limit:
        return content
    return content[:limit].rstrip() + "…"


def generate_ai_insights(job_title: str, resume_text: str) -> Dict[str, Any]:
    job_title = (job_title or "").strip()
    resume_text = (resume_text or "").strip()
    if not job_title or not resume_text:
        return FALLBACK_RESPONSE.copy()

    ability_model = ability_model_generator(job_title)
    try:
        payload = _call_insight_llm(job_title, resume_text, ability_model)
    except Exception:
        return FALLBACK_RESPONSE.copy()

    insights = {
        "ability_model": ability_model,
        "resume_text": _trim(payload.get("resume_text", ""), 190),
        "short_eval": {
            "core_strengths": [
                _trim(item, 18) for item in _ensure_list(payload.get("short_eval", {}).get("core_strengths"))
            ],
            "core_weaknesses": [
                _trim(item, 18) for item in _ensure_list(payload.get("short_eval", {}).get("core_weaknesses"))
            ],
            "match_level": payload.get("short_eval", {}).get("match_level", ""),
            "match_reason": _trim(payload.get("short_eval", {}).get("match_reason", ""), 40),
        },
        "scores": {
            "total_score": float(payload.get("scores", {}).get("total_score", 0)),
            "skill_match": float(payload.get("scores", {}).get("skill_match", 0)),
            "experience_match": float(payload.get("scores", {}).get("experience_match", 0)),
            "growth_potential": float(payload.get("scores", {}).get("growth_potential", 0)),
            "stability": float(payload.get("scores", {}).get("stability", 0)),
            "score_explain": payload.get("scores", {}).get("score_explain", ""),
        },
        "evidence": _sanitize_evidence(payload.get("evidence", {})),
        "ui": {
            "row_display": _trim(payload.get("ui", {}).get("row_display", ""), 18),
            "highlights": [
                _trim(item, 4) for item in _ensure_list(payload.get("ui", {}).get("highlights"))[:2]
            ],
        },
        "fallback": False,
    }
    return insights

