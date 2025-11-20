from __future__ import annotations

from copy import deepcopy
from typing import List, Tuple

from backend.configs.competency_strategy import COMPETENCY_STRATEGY

STRATEGY_ALIASES = {
    "销售": [
        "销售", "课程顾问", "招生", "电话销售", "电销", "BD", "招生顾问", "销售顾问", "学业规划师", "续费顾问"
    ],
    "班主任": [
        "班主任", "学管", "学业导师", "学习督导", "学服", "教务班主任", "班主任老师"
    ],
    "教研": [
        "教研", "课程研发", "教材研发", "命题", "教案", "培训师", "课程设计"
    ],
    "市场": [
        "市场", "营销", "品牌", "推广", "投放", "新媒体", "内容运营", "增长", "拉新", "传播"
    ],
    "运营": [
        "运营", "项目经理", "活动运营", "用户运营", "客服", "服务运营", "社群", "运营专员", "运营经理"
    ],
    "产品": [
        "产品", "PM", "产品经理", "产品设计", "产品策划", "需求分析"
    ],
    "职能": [
        "HR", "人力", "人事", "行政", "财务", "法务", "采购", "总务"
    ],
}

REQUIRED_DIMENSION_TEMPLATES = {
    "抗压能力": {
        "name": "抗压能力",
        "weight": 0.2,
        "desc": "在高压与高节奏的业务场景下保持稳定情绪，能够自我调节并坚持完成目标。",
        "anchors": {
            "20": "在压力情境中易受情绪影响，需要他人频繁提醒才能完成基础任务。",
            "60": "能在多数高压场景下稳住情绪，按时完成目标任务但需要适度支持。",
            "100": "面对高强度挑战仍保持积极心态，主动拆解问题并推动团队确保目标落地。",
        },
    },
    "AI工具使用能力": {
        "name": "AI工具使用能力",
        "weight": 0.2,
        "desc": "能够熟练选择并应用各类 AI / 智能工具提升教研与教学效率。",
        "anchors": {
            "20": "仅能在指导下完成基础工具操作，缺乏结合场景的使用思路。",
            "60": "可以自主选择合适工具解决常规问题，并为教学/教研工作提供支持。",
            "100": "主动探索并迭代 AI 工具策略，显著提升教研产出质量与效率并分享最佳实践。",
        },
    },
    "团队协作能力": {
        "name": "团队协作能力",
        "weight": 0.2,
        "desc": "跨部门协同推进业务目标，能够清晰沟通、主动反馈并驱动资源整合。",
        "anchors": {
            "20": "能在明确指令下完成分配任务，但对跨部门沟通缺乏主动性。",
            "60": "能与团队成员保持顺畅配合，及时同步信息并解决常见协作问题。",
            "100": "在复杂协作场景中主动协调资源、建立机制并持续优化团队协作效率。",
        },
    },
}

CATEGORY_REQUIRED_DIMENSIONS = {
    "销售": ["抗压能力"],
    "班主任": ["抗压能力"],
    "教研": ["AI工具使用能力"],
    "教师": ["AI工具使用能力"],
    "市场": ["团队协作能力"],
    "运营": ["团队协作能力"],
    "产品": ["团队协作能力"],
    "职能": ["团队协作能力"],
}


def determine_competency_strategy(job_title: str) -> Tuple[str, List[str]]:
    """
    根据岗位名称推断能力策略分类，并返回对应的维度名称列表。
    若未匹配，返回 (“通用维度”, [])，由 AI 自适应生成 5 个能力项。
    """
    title = (job_title or "").strip()
    lowered = title.lower()
    for category, keywords in STRATEGY_ALIASES.items():
        for kw in keywords:
            if kw.lower() in lowered:
                dims = COMPETENCY_STRATEGY.get(category, {}).get("dimensions", [])
                if dims:
                    return category, dims
                break
    # 默认返回通用维度（AI 自适应生成）
    return "通用维度", []


def strategy_to_clean_family(category: str) -> str:
    """
    将策略分类映射到文本清洗所需的家族 key。
    """
    if category in {"销售"}:
        return "sales"
    if category in {"班主任", "教研"}:
        return "teacher"
    return "generic"


def required_dimensions_for_category(category: str) -> List[str]:
    return CATEGORY_REQUIRED_DIMENSIONS.get(category, [])


def ensure_required_dimensions(dimensions: List[dict], category: str) -> List[dict]:
    """
    确保给定岗位分类下的必备能力维度存在；若缺失则补充默认模板。
    """
    if not dimensions:
        dimensions = []
    names = [str(d.get("name", "")) for d in dimensions]
    required_names = required_dimensions_for_category(category)
    additions: List[dict] = []
    for req_name in required_names:
        if any(req_name in n for n in names):
            continue
        template = REQUIRED_DIMENSION_TEMPLATES.get(req_name)
        if template:
            additions.append(deepcopy(template))
    if additions:
        dimensions = dimensions + additions
    return dimensions

