# backend/services/jd_ai.py
import json, math, re
from typing import Dict, Any, List
from backend.services.ai_client import get_client_and_cfg

# —— 统一中文维度名映射（防混入英文）——
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
            "anchors": d.get("anchors") or {}  # 评分锚点：{ "5": "...", "3": "...", "1": "..." }
        })
    # 至少三项兜底
    if len(out) < 3:
        out = [
            {"name":"专业技能/方法论","weight":0.5,"desc":"与岗位核心知识/技能的掌握与应用","anchors":{"5":"能独立拆解复杂问题并举一反三","3":"能按流程完成常规任务","1":"只能在提示下完成"}},
            {"name":"沟通表达/同理心","weight":0.25,"desc":"表达清晰、倾听与共情、跨部门协作","anchors":{"5":"表达清晰有条理，能共情并推动协作","3":"能清楚表达观点","1":"表达混乱或缺乏倾听"}},
            {"name":"执行力/主人翁","weight":0.25,"desc":"目标达成、推进落地、抗压负责","anchors":{"5":"有主人翁意识、主动拿结果","3":"按要求完成","1":"拖延或依赖他人推动"}}
        ]
    # 再次归一
    t = sum(x["weight"] for x in out) or 1.0
    for x in out:
        x["weight"] = round(x["weight"]/t, 4)
    return out

def _rescale_questions(questions: List[Dict[str, Any]], dimensions: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    # 分值总和归一到 100；字段中文化（保留内部 key）
    total = sum(int(q.get("score", 0)) for q in questions) or 100
    scaled = []
    for q in questions:
        sc = int(q.get("score", 0))
        dim_name = _cn(q.get("dimension") or "通用")
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
            "score": sc
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
            default_score = round(remaining_score / max(1, len(missing_dims)), 1) if remaining_score > 0 else 10
            
            scaled.append({
                "dimension": dim_name,
                "question": default_question,
                "points": default_points,
                "score": default_score
            })
    
    if total != 100 and len(scaled) > 0:
        # 重新计算总分
        new_total = sum(q["score"] for q in scaled)
        if new_total > 0:
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

def generate_jd_bundle(job_title: str, must: str="", nice: str="", exclude: str="") -> Dict[str, Any]:
    # 输入清洗（名称纠正）
    must = (must or "").replace("latex","LaTeX").replace("tex","LaTeX")
    nice = (nice or "").replace("latex","LaTeX").replace("tex","LaTeX")

    client, cfg = get_client_and_cfg()

    # —— 严格 JSON 模式 prompt ——（约束结构）
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
    "highlights": ["3个短亮点词，如：国一/LaTeX/竞赛带队"]
  }},
  "dimensions": [
    {{"name":"专业技能/方法论","weight":0.35,"desc":"…","anchors":{{"5":"…","3":"…","1":"…"}}}},
    {{"name":"教学能力","weight":0.25,"desc":"…","anchors":{{"5":"…","3":"…","1":"…"}}}},
    {{"name":"技术技能","weight":0.20,"desc":"…","anchors":{{"5":"…","3":"…","1":"…"}}}},
    {{"name":"沟通表达/同理心","weight":0.10,"desc":"…","anchors":{{"5":"…","3":"…","1":"…"}}}},
    {{"name":"执行力/主人翁","weight":0.10,"desc":"…","anchors":{{"5":"…","3":"…","1":"…"}}}}
  ],
  "questions": [
    {{"dimension":"专业技能/方法论","question":"…","points":["评分要点1","要点2"],"score":12}},
    {{"dimension":"教学能力","question":"…","points":["…"],"score":10}},
    {{"dimension":"技术技能","question":"…","points":["…"],"score":8}}
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
    """

    # 请求
    res = client.chat.completions.create(
        model=cfg.model,
        messages=[{"role":"user","content": user_prompt}],
        temperature=0.6,
        response_format={"type": "json_object"}
    )
    data = json.loads(res.choices[0].message.content)

    # —— 归一 & 渲染 —— 
    dims = _norm_weights(data.get("dimensions") or [])
    questions = _rescale_questions(data.get("questions") or [], dimensions=dims)
    jd = data.get("jd") or {"title": job_title}

    jd_long = _render_long_jd(jd)
    jd_short = _render_short_jd(jd)

    policy = data.get("policy") or {"total":100,"bands":[
        {"min":85,"max":100,"decision":"录用"},
        {"min":70,"max":84,"decision":"复试"},
        {"min":0,"max":69,"decision":"淘汰"},
    ]}

    rubric = {"job": job_title, "dimensions": [{"name":d["name"], "weight": d["weight"], "description": d.get("desc", "")} for d in dims]}

    return {
        "jd_long": jd_long,
        "jd_short": jd_short,
        "dimensions": dims,          # 每项含 anchors(1/3/5)
        "interview": questions,      # 每题含 points、score
        "scoring_policy": policy,
        "rubric": rubric
    }
