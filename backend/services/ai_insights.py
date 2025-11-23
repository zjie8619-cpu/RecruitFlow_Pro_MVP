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
    "score_detail": {
        "skill_match": {"score": 0, "evidence": []},
        "experience_match": {"score": 0, "evidence": []},
        "stability": {"score": 0, "evidence": []},
        "growth_potential": {"score": 0, "evidence": []},
        "final_score": 0,
    },
    "risks": [],
    "persona_tags": [],
    "resume_mini": "",
    "match_summary": "信息不足，无法评估",
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


def _call_insight_llm(job_title: str, resume_text: str, ability_model: Dict[str, Any], jd_text: str = "") -> Dict[str, Any]:
    client, cfg = get_client_and_cfg()
    prompt = textwrap.dedent(
        f"""
        你现在是一名专业的 AI 招聘评估官（能力模型专家 + 简历分析专家）。
        请基于岗位 JD 和候选人简历，按照下述结构化规则输出结果。

        【岗位名称】
        {job_title}

        【岗位 JD】
        {jd_text if jd_text else "未提供详细JD"}

        【岗位能力模型（参考）】
        {json.dumps(ability_model, ensure_ascii=False, indent=2)}

        【候选人简历】
        {resume_text}

        ----------------------------------------------
        【评分核心原则】
        ----------------------------------------------
        1. 不要凭空想象，不要虚构信息。
        2. 所有评分必须基于"简历中的真实证据"。
        3. 若无证据，则不给分或标记为 0。
        4. 每个维度都必须输出"动作证据 + 原文引用 + 推理理由"。
        5. 输出越结构化越好，方便前端展示。

        ----------------------------------------------
        【评分维度（每个维度 0-25 分）】
        ----------------------------------------------
        ① 技能匹配度（0–25 分）
        - 与岗位要求的核心技能吻合度
        - 电话/沟通/表达/复盘/服务等动作
        - 证据必须来源于简历

        ② 经验相关性（0–25 分）
        - 与行业/岗位的经验相关度
        - 是否做过类似工作、相似流程
        - 必须引用简历中的行为或经历

        ③ 稳定性（0–25 分）
        - 任职时长
        - 跳槽频率
        - 能否长期胜任岗位场景

        ④ 成长潜力（0–25 分）
        - 学习意愿
        - 表达总结能力
        - 扩展能力标志（跨岗位学习、项目总结等）

        ----------------------------------------------
        【证据链抽取规则】
        ----------------------------------------------
        请从简历中提取可以作为证据的"动作行为"，例如：
        - 电话回访、跟进家长、群接龙管理、学习督导
        - 复盘、记录问题、阅读理解、总结报告
        - 客情维护、服务跟踪
        - 任何岗位相关的行为词

        每条证据必须包含：
        {{
          "action": "识别的动作",
          "resume_quote": "简历中对应的原文片段",
          "reason": "该动作与岗位的关系解释"
        }}

        ----------------------------------------------
        【风险识别（最多 3 条）】
        ----------------------------------------------
        请识别并输出最多 3 条风险：
        - 跳槽频繁
        - 任期短
        - 行业不匹配
        - 能力缺失（根据 JD）
        - 与岗位关键动作无证据支撑

        格式：
        {{
          "risk_type": "风险类型",
          "evidence": "对应的简历内容",
          "reason": "风险原因说明"
        }}

        ----------------------------------------------
        【人才画像标签（3-6 个）】
        ----------------------------------------------
        基于整体证据自动生成 3–6 个标签，让 HR 一眼看懂候选人特征，例如：
        - 沟通型
        - 行动力强
        - 客户导向
        - 教育经验弱
        - 稳定性一般

        ----------------------------------------------
        【最终需要输出的 JSON 结构】
        ----------------------------------------------
        请严格输出以下 JSON，不要多字段，不要缺字段：

        {{
          "score_detail": {{
            "skill_match": {{
              "score": <0-25>,
              "evidence": [
                {{
                  "action": "识别的动作",
                  "resume_quote": "简历原文片段",
                  "reason": "该动作与岗位的关系"
                }}
              ]
            }},
            "experience_match": {{
              "score": <0-25>,
              "evidence": [
                {{
                  "action": "识别的动作",
                  "resume_quote": "简历原文片段",
                  "reason": "该动作与岗位的关系"
                }}
              ]
            }},
            "stability": {{
              "score": <0-25>,
              "evidence": [
                {{
                  "action": "任职时长/跳槽频率等",
                  "resume_quote": "简历原文片段",
                  "reason": "稳定性分析"
                }}
              ]
            }},
            "growth_potential": {{
              "score": <0-25>,
              "evidence": [
                {{
                  "action": "学习/总结/扩展等动作",
                  "resume_quote": "简历原文片段",
                  "reason": "成长潜力分析"
                }}
              ]
            }},
            "final_score": <0-100>
          }},
          "risks": [
            {{
              "risk_type": "风险类型",
              "evidence": "简历内容",
              "reason": "风险原因"
            }}
          ],
          "persona_tags": ["标签1", "标签2", "标签3"],
          "resume_mini": "简历的简短 2–3 行摘要",
          "match_summary": "一句话总结（推荐/需重点关注/不匹配）"
        }}

        ----------------------------------------------
        【注意事项】
        ----------------------------------------------
        - 所有分数必须基于证据链
        - resume_mini 应为简历的简短 2–3 行摘要
        - match_summary 应为一句话总结（推荐/需重点关注/不匹配）
        - 不要输出额外解释文本，只输出 JSON
        - final_score = skill_match + experience_match + stability + growth_potential
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


def generate_ai_insights(job_title: str, resume_text: str, jd_text: str = "") -> Dict[str, Any]:
    job_title = (job_title or "").strip()
    resume_text = (resume_text or "").strip()
    jd_text = (jd_text or "").strip()
    if not job_title or not resume_text:
        return FALLBACK_RESPONSE.copy()

    ability_model = ability_model_generator(job_title)
    try:
        payload = _call_insight_llm(job_title, resume_text, ability_model, jd_text)
    except Exception as e:
        import sys
        print(f"[ERROR] AI insights generation failed: {e}", file=sys.stderr)
        return FALLBACK_RESPONSE.copy()

    # 解析新的 score_detail 格式
    score_detail = payload.get("score_detail", {})
    if not score_detail:
        # 兼容旧格式
        old_scores = payload.get("scores", {})
        score_detail = {
            "skill_match": {"score": float(old_scores.get("skill_match", 0)), "evidence": []},
            "experience_match": {"score": float(old_scores.get("experience_match", 0)), "evidence": []},
            "stability": {"score": float(old_scores.get("stability", 0)), "evidence": []},
            "growth_potential": {"score": float(old_scores.get("growth_potential", 0)), "evidence": []},
            "final_score": float(old_scores.get("total_score", 0)),
        }

    # 提取各维度分数（用于兼容旧代码）
    skill_score = float(score_detail.get("skill_match", {}).get("score", 0))
    exp_score = float(score_detail.get("experience_match", {}).get("score", 0))
    stability_score = float(score_detail.get("stability", {}).get("score", 0))
    growth_score = float(score_detail.get("growth_potential", {}).get("score", 0))
    final_score = float(score_detail.get("final_score", skill_score + exp_score + stability_score + growth_score))

    # 规范化到 0-100 分制（用于显示）
    normalized_scores = {
        "skill_match": round(skill_score / 25.0 * 100.0, 1) if skill_score > 0 else 0.0,
        "experience_match": round(exp_score / 25.0 * 100.0, 1) if exp_score > 0 else 0.0,
        "stability": round(stability_score / 25.0 * 100.0, 1) if stability_score > 0 else 0.0,
        "growth_potential": round(growth_score / 25.0 * 100.0, 1) if growth_score > 0 else 0.0,
        "total_score": round(final_score, 1),
    }

    insights = {
        "ability_model": ability_model,
        "resume_text": _trim(payload.get("resume_mini", payload.get("resume_text", "")), 190),
        "short_eval": {
            "core_strengths": [
                _trim(item, 18) for item in _ensure_list(payload.get("short_eval", {}).get("core_strengths"))
            ],
            "core_weaknesses": [
                _trim(item, 18) for item in _ensure_list(payload.get("short_eval", {}).get("core_weaknesses"))
            ],
            "match_level": payload.get("short_eval", {}).get("match_level", ""),
            "match_reason": _trim(payload.get("short_eval", {}).get("match_reason", payload.get("match_summary", "")), 40),
        },
        "scores": normalized_scores,  # 规范化后的分数（0-100）
        "score_detail": score_detail,  # 原始分数（0-25）和证据链
        "risks": payload.get("risks", []),
        "persona_tags": payload.get("persona_tags", []),
        "match_summary": payload.get("match_summary", ""),
        "evidence": _sanitize_evidence(payload.get("evidence", {})),
        "ui": {
            "row_display": _trim(payload.get("ui", {}).get("row_display", ""), 18),
            "highlights": [
                _trim(item, 4) for item in _ensure_list(payload.get("ui", {}).get("highlights") or payload.get("persona_tags", []))[:2]
            ],
        },
        "fallback": False,
    }
    return insights

