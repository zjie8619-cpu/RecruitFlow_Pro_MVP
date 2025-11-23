def ai_score_one(client, cfg, jd_text: str, resume_text: str, job_title: str = "") -> Dict[str, Any]:
    """综合启发式匹配和智能诊断，输出统一结构。"""
    safe_resume_text = _safe_str(resume_text or "")
    heuristic_scores = _heuristic_score_from_text(jd_text, safe_resume_text, job_title)
    data = dict(heuristic_scores)

    insights = generate_ai_insights(job_title, safe_resume_text)
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
        data["证据"] = json.dumps(evidence_struct, ensure_ascii=False)

    def _apply_ui():
        ui_struct = insights.get("ui") or {"row_display": "", "highlights": []}
        data["summary_for_ui"] = ui_struct

    data["resume_mini"] = insights.get("resume_text", "")

    if not insights.get("fallback"):
        _merge_scores()
    else:
        data["总分"] = 0
        data["维度得分"] = {"技能匹配度": 0, "经验相关性": 0, "成长潜力": 0, "稳定性": 0}
        data["score_explain"] = ""

    _apply_short_eval()
    _apply_evidence()
    _apply_ui()

    return data

