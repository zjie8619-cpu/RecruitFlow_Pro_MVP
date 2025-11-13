import json
from typing import Any, Dict

import pandas as pd

from backend.services.ai_client import get_client_and_cfg
from backend.utils.sanitize import sanitize_ai_output, SYSTEM_PROMPT
from backend.services.text_rules import sanitize_for_job


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


def ai_score_one(client, cfg, jd_text: str, resume_text: str, job_title: str = "") -> Dict[str, Any]:
    # 使用统一的防幻觉系统提示词
    prompt = f"""
你是资深招聘面试官。请基于下面信息对候选人进行匹配评分，返回中文 JSON，且只返回 JSON：

【岗位 JD】
{jd_text}

【候选人简历】
{resume_text[:8000]}

评分口径（总分 100）：
- 技能匹配度（30）
- 经验相关性（30）
- 成长潜力（20）
- 稳定性与岗位适配性（20）

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
    res = client.chat.completions.create(
        model=_get_model(cfg),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=_get_temperature(cfg),
        response_format={"type": "json_object"},
    )
    data = json.loads(res.choices[0].message.content)
    
    # 🚫 防幻觉过滤：清理"证据"和"简评"
    if job_title:
        # 第一层：使用 sanitize_ai_output 进行基础清理
        evidence_list = data.get("证据", [])
        cleaned_evidence = [sanitize_ai_output(ev, job_title) for ev in evidence_list]
        cleaned_evidence = [ev for ev in cleaned_evidence if ev]  # 移除空字符串
        
        # 将证据列表合并为字符串，用于岗位级清洗
        evidence_text = "；".join(cleaned_evidence)
        summary_text = sanitize_ai_output(data.get("简评", ""), job_title)
        
        # 第二层：使用 sanitize_for_job 进行岗位级清洗（针对销售/课程顾问等岗位）
        evidence_text, summary_text = sanitize_for_job(job_title, evidence_text, summary_text)
        
        # 将清洗后的证据文本重新拆分为列表
        data["证据"] = [ev.strip() for ev in evidence_text.split("；") if ev.strip()]
        data["简评"] = summary_text
    
    return data


def ai_match_resumes_df(jd_text: str, resumes_df: pd.DataFrame, job_title: str = "") -> pd.DataFrame:
    client, cfg = get_client_and_cfg()
    rows = []
    for _, row in resumes_df.iterrows():
        text = row.get("text", "")
        try:
            result = ai_score_one(client, cfg, jd_text, text, job_title)
        except Exception as e:
            result = {
                "总分": 0,
                "维度得分": {"技能匹配度": 0, "经验相关性": 0, "成长潜力": 0, "稳定性": 0},
                "证据": [],
                "简评": f"AI评分失败：{e}",
            }
        rows.append(
            {
                "candidate_id": row.get("candidate_id"),
                "file": row.get("file"),
                "email": row.get("email", ""),
                "phone": row.get("phone", ""),
                "总分": result.get("总分", 0),
                "技能匹配度": result.get("维度得分", {}).get("技能匹配度", 0),
                "经验相关性": result.get("维度得分", {}).get("经验相关性", 0),
                "成长潜力": result.get("维度得分", {}).get("成长潜力", 0),
                "稳定性": result.get("维度得分", {}).get("稳定性", 0),
                "简评": result.get("简评", ""),
                "证据": "；".join(result.get("证据") or []),
                "text_len": row.get("text_len", 0),
            }
        )

    df = pd.DataFrame(rows)
    
    # 🚫 岗位级清洗：对"证据"和"简评"进行最终清洗（针对销售/课程顾问等岗位）
    if job_title and not df.empty:
        if "证据" in df.columns and "简评" in df.columns:
            cleaned_evidence = []
            cleaned_summary = []
            for ev, sm in zip(df["证据"].fillna(""), df["简评"].fillna("")):
                ev2, sm2 = sanitize_for_job(job_title, str(ev), str(sm))
                cleaned_evidence.append(ev2)
                cleaned_summary.append(sm2)
            df["证据"] = cleaned_evidence
            df["简评"] = cleaned_summary
            
            # 若经过清洗导致"证据/简评"被清空，但得分仍然较高，做一次惩罚性收敛，避免空证据高分
            for col in ["技能匹配度", "经验相关性", "成长潜力", "稳定性"]:
                if col in df.columns:
                    df.loc[(df["证据"].astype(str).str.len() < 2) & (df[col] > 15), col] = 15
            if "总分" in df.columns:
                df.loc[(df["证据"].astype(str).str.len() < 2) & (df["总分"] > 70), "总分"] = 70
    
    return df

