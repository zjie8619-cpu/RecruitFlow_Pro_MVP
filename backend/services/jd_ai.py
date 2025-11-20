# backend/services/jd_ai.py
import json, re
from copy import deepcopy
from typing import Dict, Any, List

from backend.services.ai_client import get_client_and_cfg, chat_completion
from backend.services.competency_utils import (
    determine_competency_strategy,
    strategy_to_clean_family,
    ensure_required_dimensions,
    REQUIRED_DIMENSION_TEMPLATES,
    required_dimensions_for_category,
)
from backend.services.text_rules import strip_competition_terms


NAME_MAP = {
    "Communication": "沟通表达/同理心",
    "Execution": "执行力/主人翁",
    "Ownership": "执行力/主人翁",
    "Analytical": "数据分析/结果导向",
    "Methodology": "专业技能/方法论",
    "Growth": "学习成长/潜力",
    "Teaching": "教学能力",
    "Tech": "技术技能",
}

SYSTEM_PROMPT_COMPETENCY = """你是一名岗位能力模型设计专家。请根据输入信息生成 5 个岗位能力维度。

必须遵守：
1. 始终输出 5 个能力维度。若已提供固定维度列表，需按给定顺序逐条输出；若未提供，请结合岗位信息自行设计 5 个高度相关的能力项。
2. 每个能力维度必须包含：
   - "维度名称"
   - "定义"：40-60 字专业描述，强调岗位相关行为与产出；
   - "权重"：数字，允许一位小数，所有维度权重求和需等于 100；
   - "评分锚点"：一个对象，键名固定为 "20"、"60"、"100"，分别描述该维度在 20 分（基础达成）、60 分（良好达成）、100 分（优秀达成）时的可观察行为表现，需避免套话；
   - "面试题"：数组形式，至少 1 条开放式问题；
   - "评分要点"：数组形式，2-4 条要点，帮助评委快速判断答案优劣。
3. 如提供“必须包含的能力维度”，需确保这些名称全部出现在最终 5 个维度中，可调整定义、权重及锚点描述。
4. 所有文本需紧贴岗位场景，可量化、可验证；禁止输出与岗位无关或空泛模板化内容。
5. 输出必须是合法 JSON，不得包含额外解释、注释或 Markdown。"""

DEVELOPER_PROMPT_COMPETENCY = """# Developer Rules
1. 固定维度若存在，名称顺序必须与输入一致；禁止遗漏或新增名称。
2. 若提供必选能力维度（如抗压能力 / AI工具使用能力 / 团队协作能力），必须确保它们出现在 5 个维度中。
3. 权重字段只能为数字，允许 1 位小数，最终总和需为 100。
4. "评分锚点" 对象必须同时包含 "20"、"60"、"100" 三个键，并体现行为层级差异。
5. "面试题" 与 "评分要点" 必须使用数组承载文本。
6. JSON 必须可解析且仅返回 JSON 对象，禁止输出额外说明。"""

def _cn(s: str) -> str:
    s = (s or "").strip()
    return NAME_MAP.get(s, s)

def generate_default_question(dimension_name: str) -> str:
    """AI 无返回时的默认题目模板"""
    default_questions = {
        "沟通表达/同理心": "请举例说明你在与同事或客户沟通中，如何理解并回应他人情绪与需求。",
        "执行力/主人翁": "请描述一次你面对工作挑战时主动承担责任并推动任务完成的经历。",
        "执行力/主人翁精神": "请描述一次你面对工作挑战时主动承担责任并推动任务完成的经历。",
        "专业技能/方法论": "请分享一个你运用专业知识解决复杂问题的实际案例，说明你的思考过程和方法。",
        "数据分析/结果导向": "请描述一次你通过数据分析发现问题并推动业务改进的经历。",
        "学习成长/潜力": "请分享一个你快速学习新技能并应用到工作中的例子。",
        "教学能力": "请描述一次你向他人传授知识或技能的经历，说明你的教学方法。",
        "技术技能": "请举例说明你在技术项目中解决关键问题的经历。"
    }
    return default_questions.get(dimension_name, f"请结合{dimension_name}维度，描述一个相关的典型工作场景。")

def generate_default_rubric(dimension_name: str) -> List[str]:
    """AI 无返回时的默认评分要点"""
    default_rubrics = {
        "沟通表达/同理心": ["表达清晰；倾听他人；共情回应；解决冲突能力强。"],
        "执行力/主人翁": ["责任心强；积极主动；执行高效；能带动团队完成目标。"],
        "执行力/主人翁精神": ["责任心强；积极主动；执行高效；能带动团队完成目标。"],
        "专业技能/方法论": ["回答逻辑清晰；有实际案例；体现核心能力；方法科学有效。"],
        "数据分析/结果导向": ["数据敏感度高；分析逻辑清晰；能提出可行方案；结果可量化。"],
        "学习成长/潜力": ["学习能力强；适应速度快；有持续改进意识；展现成长潜力。"],
        "教学能力": ["表达清晰易懂；方法科学有效；能因材施教；学员反馈良好。"],
        "技术技能": ["技术深度足够；解决思路清晰；有实际项目经验；技术选型合理。"]
    }
    return default_rubrics.get(dimension_name, ["回答逻辑清晰；有实际案例；体现核心能力。"])

def _split_points(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"[；;、\n]", text)
    return [p.strip() for p in parts if p.strip()]

def _competency_json_to_internal(data: Dict[str, Any]) -> Dict[str, Any]:
    """将能力模型 JSON 转换成内部 dimensions/interview 结构"""
    abilities = data.get("能力模型") or []
    dimensions = []
    questions = []
    for ability in abilities:
        name = str(ability.get("维度名称") or "").strip()
        weight_pct = float(ability.get("权重", 0))
        definition = str(ability.get("定义", "")).strip()

        anchors_raw = ability.get("评分锚点") or {}
        if isinstance(anchors_raw, dict):
            anchor_20 = anchors_raw.get("20") or anchors_raw.get("twenty") or ""
            anchor_60 = anchors_raw.get("60") or anchors_raw.get("sixty") or ""
            anchor_100 = anchors_raw.get("100") or anchors_raw.get("one_hundred") or ""
        else:
            anchors_raw = {}
            anchor_20 = ""
            anchor_60 = ""
            anchor_100 = ""

        # 兼容旧字段
        anchor_100 = anchor_100 or anchors_raw.get("5") or ability.get("五分表现") or ability.get("优秀表现") or ""
        anchor_60 = anchor_60 or anchors_raw.get("3") or ability.get("三分表现") or ability.get("良好表现") or ""
        anchor_20 = anchor_20 or anchors_raw.get("1") or ability.get("一分表现") or ability.get("低分表现") or ""

        interview_questions = ability.get("面试题") or []
        if isinstance(interview_questions, str):
            interview_questions = [q.strip() for q in re.split(r"[；;、\n]", interview_questions) if q.strip()]
        elif isinstance(interview_questions, list):
            interview_questions = [str(q).strip() for q in interview_questions if str(q).strip()]
        else:
            interview_questions = []

        scoring_field = ability.get("评分要点", [])
        if isinstance(scoring_field, str):
            scoring_notes = _split_points(scoring_field)
        elif isinstance(scoring_field, list):
            scoring_notes = [str(item).strip() for item in scoring_field if str(item).strip()]
        else:
            scoring_notes = []
        if not scoring_notes:
            scoring_notes = ["具备扎实案例支撑，能够量化结果。"]

        dimensions.append({
            "name": name,
            "weight": round(weight_pct / 100.0, 4),
            "desc": definition,
            "anchors": {
                "20": anchor_20 or "基础满足岗位要求，但缺乏稳定性或仍需他人指导。",
                "60": anchor_60 or "能够稳定完成核心职责，出现亮点并主动复盘改进。",
                "100": anchor_100 or "持续交付卓越成果，能量化产生影响并带动他人提升。",
            }
        })
        question_text = interview_questions[0] if interview_questions else f"请结合你的{name}，分享一个代表性的案例。"
        questions.append({
            "dimension": name,
            "question": question_text,
            "points": scoring_notes,
            "score": round(weight_pct, 1) if weight_pct else 20.0,
        })
    return {"dimensions": dimensions, "questions": questions}

EXTRACT_SYSTEM_PROMPT = """你是一名「岗位 JD 精准提取 + 能力模型分析引擎」。必须严格遵守：
1) 短版JD只能来自长版JD，做提炼不做创造（40-80字）。
2) 能力维度只能从“任职要求”抽象总结，禁止凭空新增。
3) 每个能力维度需包含权重、评分锚点（20/60/100 档）、面试题与评分要点，且均基于原文信息。
4) 严格输出指定 JSON 结构，字段名不可变更，总数固定为 5 个能力维度。
"""

EXTRACT_DEVELOPER_PROMPT = """# Developer rules（必须执行）
1. 输出必须符合 JSON 结构：short_jd、能力维度、能力维度_面试题。
2. “能力维度”数组长度固定为 5；每项需包含 维度名称、定义、权重、评分锚点(20/60/100)、面试题、评分要点。
3. 所有内容必须从长版 JD 中提取或抽象，不允许凭空创造或加入模板化无关项。
4. “评分锚点” 对象必须包含 "20"、"60"、"100" 三个键，描述可观察的行为差异；“评分要点” 必须为数组。
5. JSON 必须可解析，不能包含额外解释文字。
"""

def extract_short_and_competencies_from_long_jd_llm(full_jd: str, job_title: str) -> Dict[str, Any]:
    """从长版JD中抽取短版JD与基于任职要求的能力维度与面试题"""
    client, cfg = get_client_and_cfg()
    text = full_jd or ""
    # 简单分段：任职要求、职责
    parts = re.split(r"任职要求[:：]?", text, maxsplit=1)
    duties = parts[0].strip()
    requires = parts[1].strip() if len(parts) > 1 else text
    user_prompt = f"""请按照系统要求，以“长版 JD”为唯一依据，生成短版 JD、岗位能力维度、以及面试题：

【岗位职责】
{duties}

【任职要求】
{requires}

必须输出 JSON：
{{
  "short_jd": "",
  "能力维度": [
    {{"维度名称": "", "定义": "", "权重": 0, "评分锚点": {{"20": "", "60": "", "100": ""}}}}
  ],
  "能力维度_面试题": [
    {{"维度名称": "", "面试题": "", "评分要点": "", "分值": 0}}
  ]
}}"""
    res = chat_completion(
        client,
        cfg,
        messages=[
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {"role": "system", "content": EXTRACT_DEVELOPER_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    data = json.loads(res.choices[0].message.content)
    # 规范化：权重与分值
    dims = data.get("能力维度") or []
    total_w = sum(float(d.get("权重", 0)) for d in dims) or 100.0
    if dims:
        for d in dims:
            d["权重"] = round(100.0 * float(d.get("权重", 0)) / total_w, 1)
    qs = data.get("能力维度_面试题") or []
    total_s = sum(float(q.get("分值", 0)) for q in qs) or 100.0
    if qs:
        for q in qs:
            q["分值"] = round(100.0 * float(q.get("分值", 0)) / total_s, 1)
    # 兼容调用：补充简单版输出字段
    try:
        data["competencies"] = [d.get("维度名称","") for d in data.get("能力维度", []) if d.get("维度名称")]
    except Exception:
        data["competencies"] = []
    if not data.get("short_jd"):
        # 如果模型未返回短版JD，回退用职责首句提炼
        first_line = duties.splitlines()[0] if duties else ""
        data["short_jd"] = (first_line[:70] + "…") if len(first_line) > 70 else first_line
    return data

def extract_short_and_competencies_from_long_jd_single(full_jd: str) -> dict:
    # 一参版本：关键词轻量规则（不生成竞赛/教练/LaTeX等无关内容）
    text = (full_jd or "").lower()
    if any(k in text for k in ["前端", "html", "vue", "react", "javascript"]):
        return {
            "short_jd": "负责前端页面功能开发与交互优化，保障高质量交付与良好体验。",
            "competencies": ["专业技能/方法论", "技术能力", "沟通表达", "执行力"]
        }
    if "java" in text:
        return {
            "short_jd": "负责 Java 业务系统开发与性能优化，定位并解决关键问题。",
            "competencies": ["专业技能/方法论", "技术能力", "分析能力", "执行力"]
        }
    if "python" in text:
        return {
            "short_jd": "负责 Python 后端开发与数据处理，实现业务逻辑并优化稳定性。",
            "competencies": ["专业技能/方法论", "技术能力", "数据分析", "执行力"]
        }
    if ("销售" in text) or ("顾问" in text):
        return {
            "short_jd": "负责客户沟通与需求分析，推进商机转化并完成销售目标。",
            "competencies": ["沟通表达", "目标意识", "服务意识", "执行力"]
        }
    if ("教务" in text) or ("班主任" in text):
        return {
            "short_jd": "负责学员管理与课程协调，提供稳定高质量的教务支持。",
            "competencies": ["沟通能力", "组织协调", "责任心", "服务意识"]
        }
    return {
        "short_jd": "负责岗位相关核心职责，推动任务落地并达成目标。",
        "competencies": ["沟通能力", "执行力", "责任心"]
    }

def extract_short_and_competencies_from_long_jd(full_jd: str, job_title: str = ""):
    """
    统一入口：如果给了 job_title，则走 LLM 精准提取；
    如果没给 job_title，则走一参轻量关键词规则。
    """
    if job_title:
        return extract_short_and_competencies_from_long_jd_llm(full_jd, job_title)
    return extract_short_and_competencies_from_long_jd_single(full_jd)

def _generate_competency_model(job_title: str, job_desc: str, category: str, fixed_dimensions: List[str]) -> Dict[str, Any]:
    """调用 LLM，基于策略维度生成 5 维度能力模型"""
    client, cfg = get_client_and_cfg()
    fixed_text = ""
    if fixed_dimensions:
        fixed_text = "\n".join([f"{idx+1}. {dim}" for idx, dim in enumerate(fixed_dimensions)])
        dimension_instruction = f"固定能力维度列表（必须按顺序逐条生成，名称不可增删）：\n{fixed_text}"
    else:
        dimension_instruction = "未提供固定能力维度，请结合岗位信息自适应生成 5 个高度相关的能力维度。"

    required_dims = required_dimensions_for_category(category)
    if required_dims:
        required_text = "必须包含以下能力维度（名称需完整保留，可根据岗位实际补充定义与锚点）：\n" + "\n".join(
            [f"- {name}" for name in required_dims]
        )
    else:
        required_text = "若无必选能力维度，可根据岗位特点自由设计其他能力项。"

    user_prompt = f"""请根据以下信息生成岗位能力模型：

岗位名称：{job_title}
岗位背景（必备/加分/排除摘要）：{job_desc or "无"}
策略分类参考：{category or "通用维度"}
{dimension_instruction}
{required_text}

输出 JSON 结构如下，必须包含 5 个能力条目，字段名不可修改：
{{
  "岗位分类": "{category or '通用维度'}",
  "能力模型": [
    {{
      "维度名称": "",
      "定义": "",
      "权重": 0,
      "评分锚点": {{
        "20": "",
        "60": "",
        "100": ""
      }},
      "面试题": ["", ""],
      "评分要点": ["", ""]
    }}
  ]
}}

遵循规则：
- 始终生成 5 个维度；若提供固定列表，必须顺序对应；否则请自适应生成与岗位强相关的维度；
- 权重为数字，允许一位小数，所有权重求和=100；
- 每条评分锚点需描述 20/60/100 分行为差异：20 分为基础达成，60 分为良好达成，100 分为优秀达成，需可观察、可量化；
- 面试题需与维度高度贴合，提问真实场景；评分要点需为 2-4 条可执行要点。
- 不得输出除 JSON 外的任何内容。"""

    res = chat_completion(
        client,
        cfg,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_COMPETENCY},
            {"role": "system", "content": DEVELOPER_PROMPT_COMPETENCY},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return json.loads(res.choices[0].message.content)
def _norm_weights(dims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # 权重归一（和=1），名称中文化
    total = sum(max(float(d.get("weight", 0.0)), 0.0) for d in dims) or 1.0
    out = []
    for d in dims:
        w = max(float(d.get("weight", 0.0)), 0.0) / total
        name = _cn(str(d.get("name", "")).strip() or "专业技能/方法论")
        out.append({
            "name": name,
            "weight": round(w, 4),
            "desc": str(d.get("desc", "")).strip(),
            "anchors": d.get("anchors") or {}  # 评分锚点：{ "20": "...", "60": "...", "100": "..." }
        })
    # 至少三项兜底
    if len(out) < 3:
        out = [
            {"name":"专业技能/方法论","weight":0.5,"desc":"与岗位核心知识/技能的掌握与应用","anchors":{"20":"在指导下完成基础任务，对核心方法理解零散。","60":"能够独立完成常规任务，并结合方法论持续优化。","100":"系统拆解复杂问题，形成可复制方法并带动团队提升。"}},
            {"name":"沟通表达/同理心","weight":0.25,"desc":"表达清晰、倾听与共情、跨部门协作","anchors":{"20":"沟通表达较为生硬，需要提醒才能完整传递信息。","60":"能够清晰表达观点并倾听反馈，协作顺畅。","100":"高效沟通并促进跨团队对齐，能处理冲突并保持共赢。"}},
            {"name":"执行力/主人翁","weight":0.25,"desc":"目标达成、推进落地、抗压负责","anchors":{"20":"按流程完成基础工作，遇到阻碍依赖他人推动。","60":"对目标主动拆解并按期交付，可在压力下保持进度。","100":"主动识别风险并快速解决，确保结果达成并复盘沉淀。"}}
        ]
    # 再次归一
    t = sum(x["weight"] for x in out) or 1.0
    for x in out:
        x["weight"] = round(x["weight"]/t, 4)
    return out

def _rescale_questions(questions: List[Dict[str, Any]], dimensions: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    # 分值总和归一到 100；字段中文化（保留内部 key）
    total = sum(float(q.get("score", 0)) for q in questions) or 100.0
    allowed_dims = []
    if dimensions:
        allowed_dims = [_cn(d.get("name", "")) for d in dimensions]
        allowed_set = set(allowed_dims)
    else:
        allowed_set = set()
    scaled = []
    for q in questions:
        sc = float(q.get("score", 0))
        dim_name = _cn(q.get("dimension") or "通用")
        # 非 coach/teacher 岗位：剔除与给定 profile 无关的维度
        if allowed_set and dim_name not in allowed_set:
            continue
        question_text = str(q.get("question","")).strip()
        
        # 🔧 修正逻辑：如果 AI 没返回内容，重新生成真实文本而非提示语
        if not question_text or question_text == "（待生成）":
            question_text = generate_default_question(dim_name)
        
        points = q.get("points") or []
        # 🔧 修正逻辑：如果评分要点为空，生成真实评分要点而非提示语
        if not points or (isinstance(points, list) and len(points) == 0):
            points = generate_default_rubric(dim_name)
        
        scaled.append({
            "dimension": _cn(q.get("dimension") or "通用"),
            "question": question_text,
            "points": points,  # 评分要点（列表）
            "score": round(sc, 1),
        })
    
    # 确保每个维度都有对应的面试题
    if dimensions:
        dim_names = {_cn(d.get("name", "")) for d in dimensions}
        existing_dims = {q["dimension"] for q in scaled}
        missing_dims = dim_names - existing_dims
        
        for dim_name in missing_dims:
            # 🔧 为缺失的维度生成真实默认面试题（而非提示语）
            default_question = generate_default_question(dim_name)
            default_points = generate_default_rubric(dim_name)
            # 计算默认分值（平均分配剩余分值）
            remaining_score = max(0, 100 - sum(q["score"] for q in scaled))
            default_score = round(remaining_score / max(1, len(missing_dims)), 1) if remaining_score > 0 else 20.0
            
            scaled.append({
                "dimension": dim_name,
                "question": default_question,
                "points": default_points,
                "score": default_score
            })
    
    if abs(total - 100.0) > 0.01 and len(scaled) > 0:
        # 重新计算总分
        new_total = sum(q["score"] for q in scaled)
        if new_total > 0 and scaled:
            for q in scaled:
                q["score"] = round(100 * (q["score"]/new_total), 1)
            # 校正四舍五入误差
            gap = 100 - sum(q["score"] for q in scaled)
            if abs(gap) > 0.01:
                scaled[0]["score"] = round(scaled[0]["score"] + gap, 1)
    return scaled

def _render_long_jd(jd: Dict[str, Any]) -> str:
    """把结构化 JD 渲染成『Boss直聘可用』长版文本"""
    title = jd.get("title") or ""
    mission = jd.get("mission") or ""
    resp = jd.get("responsibilities") or []
    req = jd.get("requirements") or {}
    kpi = jd.get("kpi") or []
    work_mode = jd.get("work_mode") or "全职"
    location = jd.get("location") or "可远程/可线下"
    salary = jd.get("salary") or "面议"
    benefits = jd.get("benefits") or []
    process = jd.get("process") or ["简历筛选","初面","复面","发放 Offer"]

    def bullets(lst): return "\n".join([f"{i+1}）{x}" for i,x in enumerate(lst) if str(x).strip()])

    must = req.get("must") or []
    nice = req.get("plus") or []
    excl = req.get("exclude") or []

    return (
f"【{title}｜岗位使命】\n{mission}\n\n"
f"【岗位职责】\n{bullets(resp)}\n\n"
f"【任职要求】\n必备：\n{bullets(must)}\n\n加分：\n{bullets(nice)}\n\n排除项（不考虑）：\n{bullets(excl)}\n\n"
f"【KPI/关键结果】\n{bullets(kpi)}\n\n"
f"【工作方式/地点】{work_mode}｜{location}\n"
f"【薪资范围】{salary}\n"
f"【福利亮点】\n{bullets(benefits)}\n\n"
f"【面试流程】\n{bullets(process)}"
    )

def _render_short_jd(jd: Dict[str, Any]) -> str:
    # 80 字内电梯话术
    title = jd.get("title") or ""
    highlights = jd.get("highlights") or []
    h = "、".join([x for x in highlights if str(x).strip()])[:30]
    mission = jd.get("mission","")[:40]
    return f"{title}｜{mission}｜{h}".strip("｜")

def _profile_to_prompt_dimensions(profile: List[Dict[str, Any]]) -> str:
    # 将能力维度 profile 转为 JSON 片段字符串，供 Prompt 使用
    lines = []
    for p in profile:
        lines.append(
            f'{{"name":"{p["name"]}","weight":{p["weight"]},"desc":"{p.get("desc","")}","anchors":{{"20":"…","60":"…","100":"…"}}}}'
        )
    return ",\n    ".join(lines)

def generate_jd_bundle(job_title: str, must: str = "", nice: str = "", exclude: str = "") -> Dict[str, Any]:
    # 输入清洗
    must = (must or "").replace("latex", "LaTeX").replace("tex", "LaTeX")
    nice = (nice or "").replace("latex", "LaTeX").replace("tex", "LaTeX")

    job_desc_summary = f"必备：{must}\n加分：{nice}\n排除：{exclude}"
    strategy_category, fixed_dimensions = determine_competency_strategy(job_title)
    competency_json = _generate_competency_model(job_title, job_desc_summary, strategy_category, fixed_dimensions)
    job_type = competency_json.get("岗位分类") or strategy_category or "通用维度"

    competency_struct = _competency_json_to_internal(competency_json)
    dims_with_required = ensure_required_dimensions(competency_struct["dimensions"], category)
    dims_internal = _norm_weights(dims_with_required)

    required_names = required_dimensions_for_category(category)

    # 保证输出 5 个维度
    if len(dims_internal) > 5:
        selected: List[Dict[str, Any]] = []
        used_names = set()
        # 先保留必选维度
        for req in required_names:
            for dim in dims_internal:
                if dim["name"] in used_names:
                    continue
                if req in dim["name"]:
                    selected.append(dim)
                    used_names.add(dim["name"])
                    break
        # 补齐剩余维度，保持原有顺序
        for dim in dims_internal:
            if dim["name"] in used_names:
                continue
            if len(selected) >= 5:
                break
            selected.append(dim)
            used_names.add(dim["name"])
        dims_internal = selected[:5]
    elif len(dims_internal) < 5:
        existing_names = {d["name"] for d in dims_internal}
        fallback_names: List[str] = []
        if fixed_dimensions:
            for name in fixed_dimensions:
                if name not in existing_names:
                    fallback_names.append(name)
                if len(fallback_names) >= 5 - len(dims_internal):
                    break
        while len(fallback_names) < 5 - len(dims_internal):
            fallback_names.append(f"通用能力{len(existing_names) + len(fallback_names) + 1}")
        for name in fallback_names:
            template = REQUIRED_DIMENSION_TEMPLATES.get(name)
            if template:
                dims_internal.append(deepcopy(template))
            else:
                dims_internal.append({
                    "name": name,
                    "weight": round(1 / 5, 4),
                    "desc": "与岗位核心工作高度相关的通用能力，需要结合实际任务衡量其贡献度。",
                    "anchors": {
                        "20": "在明确指令下完成基础动作，缺乏主动总结与优化。",
                        "60": "能够独立承担常规任务并复盘迭代，对结果负责。",
                        "100": "主动识别机会并驱动改进，持续输出高质量成果并影响团队。",
                    }
                })

    # 最终再次归一化权重
    dims_internal = _norm_weights(dims_internal)

    questions_internal = _rescale_questions(competency_struct["questions"], dims_internal)

    prompt_profile = [{"name": d["name"], "weight": round(d["weight"], 4), "desc": d.get("desc", "")} for d in dims_internal]
    dims_prompt = _profile_to_prompt_dimensions(prompt_profile)

    clean_family = strategy_to_clean_family(job_type)

    client, cfg = get_client_and_cfg()

    user_prompt = f"""
你是资深招聘专家，请按严格 JSON 结构输出，且只输出 JSON，对象结构如下：
{{
  "jd": {{
    "title": "{job_title}",
    "mission": "一句话岗位使命",
    "responsibilities": ["…", "…", "…", "…", "…"],
    "requirements": {{
      "must": ["按条列出必备项，结合：{must}"],
      "plus": ["结合加分项：{nice}"],
      "exclude": ["结合排除项：{exclude}"]
    }},
    "kpi": ["3-5条可度量项"],
    "work_mode": "全职/兼职/远程",
    "location": "城市/远程",
    "salary": "xx-xxK·x薪/面议",
    "benefits": ["…","…"],
    "process": ["简历筛选","初面","复面","发 Offer"],
    "highlights": ["3个短亮点词，与岗位强相关，禁止与岗位无关的竞赛/教学词汇"]
  }},
  "dimensions": [
    {dims_prompt}
  ],
  "questions": [
    {{"dimension":"{dims_internal[0]['name'] if dims_internal else '专业技能/方法论'}","question":"…","points":["评分要点1","要点2"],"score":12}}
  ],
  "policy": {{
    "total": 100,
    "bands": [
      {{"min":85,"max":100,"decision":"录用"}},
      {{"min":70,"max":84,"decision":"复试"}},
      {{"min":0,"max":69,"decision":"淘汰"}}
    ]
  }}
}}
严格要求：只能返回 JSON 对象，不能出现任何解释或多余文本。
补充要求：
- 能力维度必须与上方提供的 5 个维度名称保持一致（不可增删），可在权重、定义上做专业化调整。
- 请避免输出与岗位无关的竞赛/教学词汇，确保职责、要求、亮点与岗位分类高度匹配。
    """

    res = chat_completion(
        client,
        cfg,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.6,
        response_format={"type": "json_object"}
    )
    data = json.loads(res.choices[0].message.content)

    jd = data.get("jd") or {"title": job_title}

    if clean_family not in {"coach", "teacher"}:
        def _clean_text(value):
            if isinstance(value, str):
                return strip_competition_terms(value, clean_family)
            return value
        jd["mission"] = _clean_text(jd.get("mission", ""))
        jd["responsibilities"] = [strip_competition_terms(str(x), clean_family) for x in jd.get("responsibilities") or []]
        jd["requirements"] = jd.get("requirements") or {}
        for key in ["must", "plus", "exclude"]:
            jd["requirements"][key] = [strip_competition_terms(str(x), clean_family) for x in jd["requirements"].get(key, [])]
        jd["highlights"] = [strip_competition_terms(str(x), clean_family) for x in jd.get("highlights") or []]
        jd["highlights"] = [h for h in jd["highlights"] if h]
        jd["kpi"] = [strip_competition_terms(str(x), clean_family) for x in jd.get("kpi") or []]
        jd["benefits"] = [strip_competition_terms(str(x), clean_family) for x in jd.get("benefits") or []]
        jd["process"] = [strip_competition_terms(str(x), clean_family) for x in jd.get("process") or []]

    jd_long = strip_competition_terms(_render_long_jd(jd), clean_family)
    jd_short = strip_competition_terms(_render_short_jd(jd), clean_family)

    policy = data.get("policy") or {"total": 100, "bands": [
        {"min": 85, "max": 100, "decision": "录用"},
        {"min": 70, "max": 84, "decision": "复试"},
        {"min": 0, "max": 69, "decision": "淘汰"},
    ]}

    rubric = {
        "job": job_title,
        "dimensions": [{"name": d["name"], "weight": d["weight"], "description": d.get("desc", "")} for d in dims_internal]
    }

    return {
        "jd_long": jd_long,
        "jd_short": jd_short,
        "dimensions": dims_internal,
        "interview": questions_internal,
        "scoring_policy": policy,
        "rubric": rubric,
        "job_type": job_type,
        "competency_raw": competency_json
    }
