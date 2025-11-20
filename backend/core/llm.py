"""
AI 接入模块：支持 OpenAI、Claude 和 SiliconFlow
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _load_api_keys() -> Dict[str, str]:
    path = Path("backend/configs/api_keys.json")
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def call_openai(
    prompt: str,
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    base_url: Optional[str] = None,
) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError("请安装 openai：pip install openai") from exc

    api_keys = _load_api_keys()
    api_key = api_keys.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("未设置 OPENAI_API_KEY")

    client = OpenAI(api_key=api_key, base_url=base_url or "https://api.openai.com/v1")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        raise Exception(f"OpenAI API 调用失败: {exc}") from exc


def call_siliconflow(prompt: str, model: str = "deepseek-chat", temperature: float = 0.7) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError("请安装 openai：pip install openai") from exc

    api_key = os.getenv("SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    if not api_key:
        api_keys = _load_api_keys()
        api_key = api_keys.get("siliconflow_api_key")
        base_url = api_keys.get("siliconflow_base_url", base_url)
    if not api_key:
        raise ValueError("未配置 siliconflow_api_key 或 SILICONFLOW_API_KEY")

    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        raise Exception(f"SiliconFlow API 调用失败: {exc}") from exc


def call_claude(prompt: str, model: str = "claude-3-5-sonnet-20241022", temperature: float = 0.7) -> str:
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise ImportError("请安装 anthropic：pip install anthropic") from exc

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("未设置 ANTHROPIC_API_KEY")

    client = Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        raise Exception(f"Claude API 调用失败: {exc}") from exc


def _build_prompt(job: str, must: str, nice: str, exclude: str) -> str:
    input_info = f"岗位名称：{job}"
    if must:
        input_info += f"\n必备经验/技能：{must}"
    if nice:
        input_info += f"\n加分项：{nice}"
    if exclude:
        input_info += f"\n排除项：{exclude}"

    return f"""你是一位资深 HR 专家，请为岗位“{job}”生成定制 JD、能力维度和面试题。

输入信息：
{input_info}

输出格式使用 === 分隔，包含：长版JD、短版JD、能力维度(JSON)、面试题(JSON)。
确保内容与岗位强相关，权重和题目可用。
"""


def generate_jd_with_ai(
    job: str,
    must_have: str = "",
    nice_to_have: str = "",
    exclude_keywords: str = "",
    provider: str = "openai",
    model: Optional[str] = None,
) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
    if provider == "openai":
        model = model or "gpt-4o-mini"
        call_func = call_openai
    elif provider == "claude":
        model = model or "claude-3-5-sonnet-20241022"
        call_func = call_claude
    elif provider == "siliconflow":
        model = model or "deepseek-chat"
        call_func = call_siliconflow
    else:
        raise ValueError(f"不支持的 provider：{provider}")

    prompt = _build_prompt(job, must_have, nice_to_have, exclude_keywords)
    response = call_func(prompt, model=model)

    jd_long = ""
    jd_short = ""
    rubric_dict: Dict[str, Any] = {"job": job, "dimensions": []}
    interview_questions: Dict[str, Any] = {"questions": []}

    if "===" in response:
        parts = [p.strip() for p in response.split("===") if p.strip()]
        for part in parts:
            if "长版" in part or "岗位职责" in part:
                jd_long = part.split("长版", 1)[-1].strip()
            elif "短版" in part or "亮点" in part:
                jd_short = part.split("短版", 1)[-1].strip()
            elif "\"dimensions\"" in part:
                match = re.search(r"\{\s*\"dimensions\".*\}", part, re.S)
                if match:
                    try:
                        payload = json.loads(match.group(0))
                        rubric_dict["dimensions"] = payload.get("dimensions", [])
                    except Exception:
                        pass
            elif "\"questions\"" in part:
                match = re.search(r"\{\s*\"questions\".*\}", part, re.S)
                if match:
                    try:
                        payload = json.loads(match.group(0))
                        interview_questions["questions"] = payload.get("questions", [])
                    except Exception:
                        pass

    if not rubric_dict["dimensions"]:
        rubric_dict["dimensions"] = [
            {"name": "专业技能/方法论", "weight": 0.35, "description": "专业能力和方法论掌握程度"},
            {"name": "沟通表达/同理心", "weight": 0.2, "description": "沟通能力和同理心"},
            {"name": "执行力/主人翁", "weight": 0.2, "description": "执行与责任心"},
            {"name": "数据意识/结果导向", "weight": 0.15, "description": "数据意识和结果导向"},
            {"name": "学习成长/潜力", "weight": 0.1, "description": "学习能力和成长潜力"},
        ]

    if not interview_questions["questions"]:
        interview_questions["questions"] = [
            {
                "dimension": "专业技能",
                "question": "请描述一个你解决过的复杂问题，重点说明思路与结果。",
                "evaluation_criteria": "优秀：方案清晰、结果可量化；良好：能解决问题但缺乏量化；一般：描述模糊；不合格：无法回答",
                "weight": 0.25,
            }
        ]

    if not jd_long:
        jd_long = response[:1000]
    if not jd_short:
        jd_short = f"{job}｜亮点概述"

    return jd_long, jd_short, rubric_dict, interview_questions

