import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import pandas as pd


EXPORT_COLUMNS = [
    "候选人ID",
    "姓名",
    "邮箱",
    "电话",
    "简历文件名",
    "简历文本长度",
    "简历解析质量评分",
    "岗位名称",
    "岗位必备技能列表",
    "岗位加分项列表",
    "岗位排除项列表",
    "岗位标准能力模型",
    "岗位能力权重模型",
    "总分",
    "技能匹配度",
    "经验相关性",
    "成长潜力",
    "稳定性",
    "风险提示",
    "证据文本",
    "推理文本",
    "结论文本",
    "证据链JSON",
    "各维度证据链JSON",
    "标签列表",
    "核心能力标签",
    "待提升能力标签",
    "是否入选TopN",
    "TopN排名",
    "面试日期",
    "面试时间",
    "面试地点",
    "日历文件已生成",
    "邮件发送成功",
    "邮件主题",
    "邮件发送时间",
    "企业微信发送成功",
    "本轮导出批次ID",
]

JSON_FIELDS = {
    "岗位必备技能列表",
    "岗位加分项列表",
    "岗位排除项列表",
    "岗位标准能力模型",
    "岗位能力权重模型",
    "证据链JSON",
    "各维度证据链JSON",
    "标签列表",
    "核心能力标签",
    "待提升能力标签",
}

BOOL_FIELDS = {
    "是否入选TopN",
    "日历文件已生成",
    "邮件发送成功",
    "企业微信发送成功",
}


def _safe_json_loads(value: Any) -> Any:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
    return {}


def _ensure_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        loaded = _safe_json_loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _ensure_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        loaded = _safe_json_loads(value)
        if isinstance(loaded, list):
            return loaded
        if loaded:
            return [loaded]
    if value is None:
        return []
    return [value]


def _normalize_requirement_value(value: Any) -> Any:
    """将必备/加分/排除项统一为 JSON 友好格式."""
    if isinstance(value, dict):
        return value
    if isinstance(value, (list, tuple, set)):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized
    if isinstance(value, str):
        parts = [
            part.strip()
            for part in re.split(r"[，,；;、\n|/]+", value)
            if part.strip()
        ]
        return parts or value.strip()
    return value


def _prepare_job_payload(job_meta: Dict[str, Any]) -> Dict[str, Any]:
    """构建统一的岗位信息载体，方便 _coalesce 解析。"""
    payload = _ensure_dict(job_meta).copy()
    if "job_name" not in payload and "岗位名称" in payload:
        payload["job_name"] = payload["岗位名称"]

    payload.setdefault(
        "job_must_have_skills",
        _normalize_requirement_value(
            _coalesce(
                [
                    "job_must_have_skills",
                    "must_have_skills",
                    "job_must",
                    "must_have",
                    "岗位必备技能列表",
                    "必备经验/技能",
                    "必备",
                ],
                payload,
            )
        ),
    )
    payload.setdefault(
        "job_bonus_skills",
        _normalize_requirement_value(
            _coalesce(
                [
                    "job_bonus_skills",
                    "plus",
                    "nice_to_have",
                    "岗位加分项列表",
                    "加分项",
                ],
                payload,
            )
        ),
    )
    payload.setdefault(
        "job_exclude_list",
        _normalize_requirement_value(
            _coalesce(
                [
                    "job_exclude_list",
                    "exclude_keywords",
                    "exclude",
                    "排除项",
                    "不考虑",
                ],
                payload,
            )
        ),
    )
    return {k: v for k, v in payload.items() if v not in (None, "", [], {})}


def _compose_evidence_chain(record: Dict[str, Any], scoring: Dict[str, Any]) -> Dict[str, Any]:
    """在缺失字段时用推理链补齐证据链 JSON."""
    composed: Dict[str, Any] = {}
    strengths = _ensure_dict(
        record.get("strengths_reasoning_chain")
        or scoring.get("strengths_reasoning_chain")
    )
    weaknesses = _ensure_dict(
        record.get("weaknesses_reasoning_chain")
        or scoring.get("weaknesses_reasoning_chain")
    )
    if strengths:
        composed["strengths_reasoning_chain"] = strengths
    if weaknesses:
        composed["weaknesses_reasoning_chain"] = weaknesses
    chains = _ensure_dict(record.get("evidence_chains") or scoring.get("evidence_chains"))
    if chains:
        composed["evidence_chains"] = chains
    return composed


def _normalize_comm_lookup(meta: Optional[Dict[str, Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    if not isinstance(meta, dict):
        return {}
    normalized: Dict[str, Dict[str, Any]] = {}
    for raw_key, payload in meta.items():
        if not raw_key or not isinstance(payload, dict):
            continue
        key = str(raw_key).strip()
        if not key:
            continue
        normalized[key] = payload
        if "@" in key:
            normalized[key.lower()] = payload
    return normalized


def _match_comm_data(candidate: Dict[str, Any], lookup: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    if not lookup:
        return {}
    keys: List[str] = []
    candidate_id = candidate.get("candidate_id") or candidate.get("候选人ID")
    if candidate_id:
        keys.append(str(candidate_id).strip())
    email = candidate.get("email") or candidate.get("邮箱")
    if email:
        keys.append(str(email).strip())
        keys.append(str(email).strip().lower())
    file_token = candidate.get("file") or candidate.get("简历文件名")
    if file_token:
        keys.append(str(file_token).strip())
    for key in keys:
        if key and key in lookup:
            return lookup[key]
    return {}


def _coalesce(keys: Iterable[str], *sources: Dict[str, Any], default: Any = "") -> Any:
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in keys:
            if key in source:
                val = source.get(key)
                if val is None:
                    continue
                if isinstance(val, float) and pd.isna(val):
                    continue
                if isinstance(val, str):
                    cleaned = val.strip()
                    if cleaned == "":
                        continue
                    return cleaned
                return val
    return default


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if pd.isna(value):
            return ""
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _serialize_json_field(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return ""
        try:
            parsed = json.loads(trimmed)
            return json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            return json.dumps(trimmed, ensure_ascii=False)
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def _bool_label(value: Any) -> str:
    truthy = {"true", "yes", "y", "1", "是", "已生成", "success", "成功", "t", "True", "TRUE"}
    falsy = {"false", "no", "n", "0", "否", "未生成"}
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in truthy:
            return "是"
        if lowered in falsy:
            return "否"
    return "是" if value else "否"


def _split_datetime(raw: Any) -> Tuple[str, str]:
    if not raw:
        return "", ""
    if isinstance(raw, dict):
        date = raw.get("date") or raw.get("day") or ""
        time = raw.get("time") or raw.get("hour") or ""
        return (_to_text(date), _to_text(time))
    text = _to_text(raw)
    if not text:
        return "", ""
    if "," in text:
        text = text.split(",")[0].strip()
    parts = text.split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    return text, ""


def _extract_reasoning(record: Dict[str, Any], scoring: Dict[str, Any]) -> str:
    direct = _coalesce(
        ["reasoning_text", "推理文本", "ai_reasoning"],
        record,
        scoring,
    )
    if direct:
        return _to_text(direct)
    sections = []
    for chain in (
        record.get("strengths_reasoning_chain"),
        record.get("weaknesses_reasoning_chain"),
        scoring.get("strengths_reasoning_chain"),
        scoring.get("weaknesses_reasoning_chain"),
    ):
        chain_dict = _ensure_dict(chain)
        reason = chain_dict.get("ai_reasoning") or chain_dict.get("reasoning")
        if reason:
            sections.append(_to_text(reason))
    return "；".join([s for s in sections if s])


def _extract_conclusion(record: Dict[str, Any], scoring: Dict[str, Any]) -> str:
    direct = _coalesce(["conclusion_text", "结论文本"], record, scoring)
    if direct:
        return _to_text(direct)
    conclusions = []
    for chain in (
        record.get("strengths_reasoning_chain"),
        record.get("weaknesses_reasoning_chain"),
        scoring.get("strengths_reasoning_chain"),
        scoring.get("weaknesses_reasoning_chain"),
    ):
        chain_dict = _ensure_dict(chain)
        conclusion = chain_dict.get("conclusion")
        if conclusion:
            conclusions.append(_to_text(conclusion))
    return "；".join([c for c in conclusions if c])


def _extract_evidence_text(record: Dict[str, Any], scoring: Dict[str, Any]) -> str:
    direct = _coalesce(["evidence_text", "证据文本", "证据"], record, scoring)
    if direct:
        return _to_text(direct)
    evidences = []
    for chain in (
        record.get("strengths_reasoning_chain"),
        record.get("weaknesses_reasoning_chain"),
        scoring.get("strengths_reasoning_chain"),
        scoring.get("weaknesses_reasoning_chain"),
    ):
        chain_dict = _ensure_dict(chain)
        resume_evidence = chain_dict.get("resume_evidence")
        if isinstance(resume_evidence, list):
            evidences.extend([_to_text(ev) for ev in resume_evidence if ev])
        elif resume_evidence:
            evidences.append(_to_text(resume_evidence))
    return "；".join(evidences)




def build_export_row(
    candidate: Dict[str, Any],
    job_config: Dict[str, Any],
    scoring: Dict[str, Any],
    evidence_payload: Dict[str, Any],
    tags_payload: Dict[str, Any],
    interview_info: Dict[str, Any],
    batch_id: str,
) -> Dict[str, str]:
    sources = [
        candidate,
        job_config,
        scoring,
        evidence_payload,
        tags_payload,
        interview_info,
    ]

    text_length = _coalesce(
        ["text_length", "text_len", "resume_length", "文本长度"],
        *sources,
    )
    parse_quality = _coalesce(
        ["parse_quality_score", "resume_quality_score", "解析质量评分"],
        *sources,
    )
    job_title = _coalesce(
        ["job_name", "岗位名称", "position", "job_title", "岗位"],
        *sources,
    )
    must_have = _coalesce(
        ["job_must_have_skills", "must_have_skills", "must_have", "岗位必备技能列表", "必备经验/技能"],
        *sources,
    )
    nice_to_have = _coalesce(
        ["job_bonus_skills", "nice_to_have", "plus", "岗位加分项列表", "加分项"],
        *sources,
    )
    exclude_items = _coalesce(
        ["job_exclude_list", "exclude_keywords", "排除项", "岗位排除项列表"],
        *sources,
    )
    standard_model = _coalesce(
        ["standard_model", "岗位标准能力模型"],
        *sources,
    )
    weight_model = _coalesce(
        ["capability_weight_model", "ability_weight_model", "weight_matrix", "岗位能力权重模型", "score_dims"],
        *sources,
    )
    evidence_chain = _coalesce(
        ["evidence_chain", "证据链JSON"],
        *sources,
    )
    dimension_chains = _coalesce(
        ["evidence_chains", "各维度证据链JSON"],
        *sources,
    )
    tags_list = _coalesce(
        ["tags", "highlight_tags", "标签列表"],
        *sources,
    )
    persona_list = _coalesce(
        ["persona_tags", "核心能力标签"],
        *sources,
    )
    weak_list = _coalesce(
        ["weak_points", "待提升能力标签"],
        *sources,
    )

    interview_time_raw = _coalesce(
        ["interview_time", "interview_datetime", "candidate_interview_time", "面试时间"],
        *sources,
    )
    interview_date, interview_time = _split_datetime(interview_time_raw)

    if not text_length:
        resume_text = candidate.get("resume_text") or candidate.get("简历文本")
        if resume_text:
            text_length = len(str(resume_text))

    if not evidence_chain:
        evidence_chain = _compose_evidence_chain(evidence_payload, scoring)

    row = {
        "候选人ID": _to_text(_coalesce(["candidate_id", "id", "候选人ID", "序号"], *sources)),
        "姓名": _to_text(_coalesce(["name", "姓名"], *sources)),
        "邮箱": _to_text(_coalesce(["email", "邮箱"], *sources)),
        "电话": _to_text(_coalesce(["phone", "手机号", "电话"], *sources)),
        "简历文件名": _to_text(_coalesce(["file", "resume_file", "文件名"], *sources)),
        "简历文本长度": _to_text(text_length),
        "简历解析质量评分": _to_text(parse_quality),
        "岗位名称": _to_text(job_title),
        "岗位必备技能列表": _serialize_json_field(must_have),
        "岗位加分项列表": _serialize_json_field(nice_to_have),
        "岗位排除项列表": _serialize_json_field(exclude_items),
        "岗位标准能力模型": _serialize_json_field(standard_model),
        "岗位能力权重模型": _serialize_json_field(weight_model),
        "总分": _to_text(_coalesce(["总分", "score_total", "total_score"], *sources)),
        "技能匹配度": _to_text(_coalesce(["技能匹配度", "skill_match"], *sources)),
        "经验相关性": _to_text(_coalesce(["经验相关性", "experience_match"], *sources)),
        "成长潜力": _to_text(_coalesce(["成长潜力", "growth_potential"], *sources)),
        "稳定性": _to_text(_coalesce(["稳定性", "stability"], *sources)),
        "风险提示": _to_text(_coalesce(["risk_alert", "风险提示"], *sources)),
        "证据文本": _extract_evidence_text(evidence_payload, scoring),
        "推理文本": _extract_reasoning(evidence_payload, scoring),
        "结论文本": _extract_conclusion(evidence_payload, scoring),
        "证据链JSON": _serialize_json_field(evidence_chain),
        "各维度证据链JSON": _serialize_json_field(dimension_chains),
        "标签列表": _serialize_json_field(tags_list),
        "核心能力标签": _serialize_json_field(persona_list or tags_list),
        "待提升能力标签": _serialize_json_field(weak_list),
        "是否入选TopN": _bool_label(_coalesce(["is_topn", "topn_flag", "入选TopN"], *sources)),
        "TopN排名": _to_text(_coalesce(["topn_rank", "TopN排名", "rank"], *sources)),
        "面试日期": interview_date,
        "面试时间": interview_time,
        "面试地点": _to_text(_coalesce(["interview_location", "面试地点", "location"], *sources)),
        "日历文件已生成": _bool_label(_coalesce(["ics_path", "日历文件已生成"], *sources)),
        "邮件发送成功": _bool_label(_coalesce(["email_sent", "邮件发送成功", "email_status"], *sources)),
        "邮件主题": _to_text(_coalesce(["email_subject", "邮件主题"], *sources)),
        "邮件发送时间": _to_text(_coalesce(["email_sent_at", "邮件发送时间"], *sources)),
        "企业微信发送成功": _bool_label(_coalesce(["wechat_sent", "企业微信发送成功", "wechat_status"], *sources)),
        "本轮导出批次ID": batch_id,
    }
    return {key: ("" if value is None else value) for key, value in row.items()}


def validate_export_csv(csv_path: str) -> None:
    df = pd.read_csv(
        csv_path,
        dtype=str,
        keep_default_na=False,
        na_values=[],
    )
    if list(df.columns) != EXPORT_COLUMNS:
        raise ValueError("导出CSV列顺序或字段集合不符合规范。")
    if df.isna().any().any():
        raise ValueError("导出CSV出现 NaN，请检查字段回填。")
    invalid_tokens = {"nan", "none", "null"}
    for col in EXPORT_COLUMNS:
        lowered = (
            df[col].astype(str).str.strip().str.lower()
            if col in df.columns
            else pd.Series(dtype=str)
        )
        if not lowered.empty and lowered.isin(invalid_tokens).any():
            raise ValueError(f"字段 {col} 存在非法取值（None/NaN）。")
    for field in BOOL_FIELDS:
        if field in df.columns:
            invalid = df[field][~df[field].isin(["是", "否", ""])]
            if not invalid.empty:
                raise ValueError(f"字段 {field} 存在非法布尔值: {invalid.unique().tolist()}")
    for field in JSON_FIELDS:
        for value in df[field]:
            if not value:
                continue
            try:
                json.loads(value)
            except Exception as exc:
                raise ValueError(f"字段 {field} JSON 解析失败: {value}") from exc


def export_round_report(
    scored_df: pd.DataFrame,
    job_meta: Optional[Dict[str, Any]] = None,
    round_meta: Optional[Dict[str, Any]] = None,
    communication_meta: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_id = f"export_batch_{ts}"
    out_dir = Path("reports")
    out_dir.mkdir(exist_ok=True, parents=True)
    csv_path = out_dir / f"recruit_round_{ts}.csv"
    xlsx_path = out_dir / f"recruit_round_{ts}.xlsx"

    records = scored_df.to_dict(orient="records") if not scored_df.empty else []
    export_rows: List[Dict[str, str]] = []
    shared_job_payload = _prepare_job_payload(job_meta or {})
    round_meta = round_meta or {}
    comm_lookup = _normalize_comm_lookup(communication_meta)
    raw_topn_ids = round_meta.get("topn_ids") or []
    topn_ids: Set[str] = {
        str(value).strip()
        for value in _ensure_list(raw_topn_ids)
        if str(value).strip()
    }
    topn_cutoff = round_meta.get("topn_cutoff")
    try:
        topn_cutoff = int(topn_cutoff) if topn_cutoff not in (None, "") else None
    except (TypeError, ValueError):
        topn_cutoff = None

    for idx, record in enumerate(records):
        base = dict(record)
        candidate_payload = {
            **base,
            **_ensure_dict(record.get("candidate_obj")),
        }
        candidate_payload.setdefault("text_length", candidate_payload.get("text_len"))
        candidate_payload["__row_index"] = idx + 1
        if not candidate_payload.get("rank"):
            candidate_payload["rank"] = (
                base.get("rank") or base.get("TopN排名") or idx + 1
            )
        candidate_id = (
            candidate_payload.get("candidate_id")
            or candidate_payload.get("id")
            or candidate_payload.get("序号")
        )
        if candidate_id is not None:
            candidate_payload["candidate_id"] = candidate_id
        if topn_ids:
            candidate_payload["is_topn"] = str(candidate_id).strip() in topn_ids
        elif topn_cutoff is not None:
            candidate_payload["is_topn"] = idx < topn_cutoff

        job_payload = {
            **shared_job_payload,
            **_ensure_dict(record.get("job_info")),
        }
        if job_payload.get("job_name") is None:
            job_payload["job_name"] = candidate_payload.get("job_name")

        scoring_payload = {
            **_ensure_dict(record.get("scoring_result")),
            "score_total": base.get("总分") or base.get("score_total"),
            "skill_match": base.get("技能匹配度") or base.get("skill_match"),
            "experience_match": base.get("经验相关性") or base.get("experience_match"),
            "growth_potential": base.get("成长潜力") or base.get("growth_potential"),
            "stability": base.get("稳定性") or base.get("stability"),
            "standard_model": _ensure_dict(record.get("standard_model")),
            "score_dims": _ensure_dict(record.get("score_dims")),
            "evidence_chains": _ensure_dict(record.get("evidence_chains")),
            "strengths_reasoning_chain": record.get("strengths_reasoning_chain"),
            "weaknesses_reasoning_chain": record.get("weaknesses_reasoning_chain"),
        }
        evidence_payload = {
            **base,
            "strengths_reasoning_chain": record.get("strengths_reasoning_chain"),
            "weaknesses_reasoning_chain": record.get("weaknesses_reasoning_chain"),
            "evidence_text": record.get("evidence_text"),
            "evidence_chains": record.get("evidence_chains"),
        }
        tags_payload = {
            **base,
            "tags": record.get("tags") or record.get("highlight_tags"),
            "persona_tags": record.get("persona_tags"),
            "weak_points": record.get("weak_points"),
            "highlight_tags": record.get("highlight_tags"),
        }
        interview_payload = {
            **base,
            **_ensure_dict(record.get("interview_info")),
        }
        comm_data = _match_comm_data(candidate_payload, comm_lookup)
        if comm_data:
            for key, value in comm_data.items():
                if value in (None, "", [], {}):
                    continue
                interview_payload[key] = value
        row = build_export_row(
            candidate_payload,
            job_payload,
            scoring_payload,
            evidence_payload,
            tags_payload,
            interview_payload,
            batch_id,
        )
        export_rows.append(row)

    export_df = pd.DataFrame(export_rows, columns=EXPORT_COLUMNS)
    export_df = export_df.fillna("")
    for bool_field in BOOL_FIELDS:
        if bool_field in export_df.columns:
            export_df[bool_field] = export_df[bool_field].apply(_bool_label)

    export_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    try:
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False, sheet_name="candidates")
    except Exception:
        pass

    validate_export_csv(str(csv_path))
    return str(csv_path)

