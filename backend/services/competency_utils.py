from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# 模板维度：用于补齐缺失的必选能力
# ---------------------------------------------------------------------------
REQUIRED_DIMENSION_TEMPLATES: Dict[str, Dict[str, object]] = {
    "沟通表达/同理心": {
        "name": "沟通表达/同理心",
        "weight": 0.22,
        "desc": "能清晰表达观点，理解对方诉求，促成共识并解决冲突。",
        "anchors": {
            "20": "表达生硬，难以确认对方需求，只能在提醒下完成沟通。",
            "60": "能清晰表达并倾听反馈，常规场景沟通顺畅。",
            "100": "能够驾驭复杂/冲突场景，快速促成对齐并带动氛围。",
        },
    },
    "客户关系管理": {
        "name": "客户关系管理",
        "weight": 0.2,
        "desc": "跟进线索、洞察需求并建立信任，保障成交与续约。",
        "anchors": {
            "20": "只能被动响应客户，缺乏需求洞察。",
            "60": "能结合客户场景提供方案，维护关键关系。",
            "100": "构建多层关系网，主动创造商机并持续复购。",
        },
    },
    "业绩结果导向": {
        "name": "业绩结果导向",
        "weight": 0.2,
        "desc": "对目标负责，拆解行动并跟踪数据，持续复盘优化。",
        "anchors": {
            "20": "完成基本指标但缺乏复盘，遇阻时依赖外部推动。",
            "60": "能拆解目标、监控进度并及时纠偏。",
            "100": "主动识别增长机会，驱动跨团队协作并超额达成。",
        },
    },
    "教学能力": {
        "name": "教学能力",
        "weight": 0.24,
        "desc": "结构化输出知识，因材施教并确保学习效果。",
        "anchors": {
            "20": "内容零散，课堂缺乏节奏。",
            "60": "能结合学员水平设计课程，课堂互动良好。",
            "100": "可沉淀方法论并提升班级整体成绩/满意度。",
        },
    },
    "学员/家长沟通": {
        "name": "学员/家长沟通",
        "weight": 0.18,
        "desc": "与学员及家长保持高频沟通，反馈进度并化解异议。",
        "anchors": {
            "20": "只能被动答疑，信息反馈不完整。",
            "60": "能主动同步学习情况，及时响应问题。",
            "100": "建立信任关系，能引导家长/学员共担目标。",
        },
    },
    "专业技能/方法论": {
        "name": "专业技能/方法论",
        "weight": 0.25,
        "desc": "掌握岗位核心知识/工具，能用方法论解决复杂问题。",
        "anchors": {
            "20": "对关键技能理解浅显，处理问题需大量指导。",
            "60": "能独立完成主要任务，并结合方法论持续优化。",
            "100": "可拆解复杂场景，沉淀可复制方案并指导他人。",
        },
    },
}

# ---------------------------------------------------------------------------
# 分类配置
# ---------------------------------------------------------------------------
CATEGORY_RULES: List[Tuple[str, List[str], List[str]]] = [
    (
        "sales",
        ["销售", "顾问", "BD", "商务", "客户成功"],
        ["沟通表达/同理心", "客户关系管理", "业绩结果导向"],
    ),
    (
        "teacher",
        ["讲师", "教研", "老师", "教练", "班主任", "辅导"],
        ["教学能力", "学员/家长沟通", "沟通表达/同理心"],
    ),
    (
        "tech",
        ["工程师", "开发", "算法", "数据", "后端", "前端", "测试"],
        ["专业技能/方法论", "执行力/主人翁"],
    ),
    (
        "product",
        ["产品", "运营", "增长", "策划"],
        ["专业技能/方法论", "数据分析/结果导向"],
    ),
]

CATEGORY_CLEAN_FAMILY = {
    "sales": "sales",
    "teacher": "coach",
    "tech": "tech",
    "product": "general",
    "general": "general",
}


def determine_competency_strategy(job_title: str) -> Tuple[str, List[str]]:
    """根据岗位名称返回策略分类和固定维度."""
    title = (job_title or "").lower()
    for category, keywords, fixed in CATEGORY_RULES:
        if any(keyword.lower() in title for keyword in keywords):
            return category, fixed
    return "general", []


def strategy_to_clean_family(category: str) -> str:
    """映射到文本清洗的 family."""
    return CATEGORY_CLEAN_FAMILY.get(category, "general")


CATEGORY_REQUIRED_MAP = {
    "sales": ["沟通表达/同理心", "客户关系管理", "业绩结果导向"],
    "teacher": ["教学能力", "学员/家长沟通"],
    "tech": ["专业技能/方法论"],
    "product": ["专业技能/方法论", "数据分析/结果导向"],
    "general": [],
}


def required_dimensions_for_category(category: str) -> List[str]:
    return CATEGORY_REQUIRED_MAP.get(category, [])


def _default_template(name: str) -> Dict[str, object]:
    template = REQUIRED_DIMENSION_TEMPLATES.get(name)
    if template:
        return deepcopy(template)
    return {
        "name": name,
        "weight": 0.2,
        "desc": f"{name}（系统默认补全）",
        "anchors": {
            "20": "仅能在指引下完成基础动作。",
            "60": "能独立完成常规任务，并按要求交付。",
            "100": "可在复杂场景下持续输出高质量成果并影响他人。",
        },
    }


def ensure_required_dimensions(
    dimensions: List[Dict[str, object]] | None,
    category: str,
) -> List[Dict[str, object]]:
    """确保分类需要的维度全部存在，并做简单归一."""
    dims: List[Dict[str, object]] = [deepcopy(d) for d in (dimensions or [])]
    existing = {str(d.get("name", "")) for d in dims}

    for name in required_dimensions_for_category(category):
        if name not in existing:
            dims.append(_default_template(name))
            existing.add(name)

    total = sum(max(float(d.get("weight", 0.0)), 0.0) for d in dims) or 1.0
    for d in dims:
        weight = max(float(d.get("weight", 0.0)), 0.0) / total
        d["weight"] = round(weight, 4)

        anchors = d.get("anchors") or {}
        for key in ("20", "60", "100"):
            anchors.setdefault(key, "")
        d["anchors"] = anchors

    return dims

# backend/services/competency_utils.py
"""
# 能力模型工具函数:用于根据岗位类型确定能力维度策略
"""
from typing import List, Tuple, Dict, Any, Literal
from copy import deepcopy
from backend.services.text_rules import infer_job_family
# 岗位分类到能力维度的映射
COMPETENCY_CATEGORIES = {
    "通用维度": {
        "required_dimensions": [],
        "fixed_dimensions": [],
    },
}

def determine_competency_strategy(job_title: str) -> Tuple[str, List[str]]:
    """
    根据岗位名称确定能力维度策略
    Args:
        job_title: 岗位名称
    Returns:
        (strategy_category, fixed_dimensions) 元组
        - strategy_category: 策略分类(如"销售"、"竞赛教练"、"教师"、"班主任"、"通用维度")
        - fixed_dimensions: 固定能力维度列表
    """
    if not job_title:
        return "通用维度", []
    job_lower = job_title.lower()
    # 判断岗位类型
    job_family = infer_job_family(job_title)
    # 根据岗位类型和关键词确定策略
    if job_family == "coach":
        return "竞赛教练", COMPETENCY_CATEGORIES.get("竞赛教练", {}).get("fixed_dimensions", [])
    elif job_family == "teacher":
        # 进一步判断是否为班主任
        if "班主任" in job_title or "班主" in job_title:
            return "班主任", COMPETENCY_CATEGORIES.get("班主任", {}).get("fixed_dimensions", [])
        else:
            return "教师", COMPETENCY_CATEGORIES.get("教师", {}).get("fixed_dimensions", [])
    elif job_family == "sales":
        return "销售", COMPETENCY_CATEGORIES.get("销售", {}).get("fixed_dimensions", [])
    else:
        # 通用维度,不提供固定维度
        return "通用维度", []
def strategy_to_clean_family(job_type: str) -> Literal["coach", "teacher", "sales", "engineer_dev", "generic"]:
    """
    将策略分类转换为清理用的 job family
    Args:
        job_type: 策略分类(如"销售"、"竞赛教练"、"教师"等)
    Returns:
        job family 字符串
    """
    mapping = {
        "销售": "sales",
        "竞赛教练": "coach",
        "教师": "teacher",
        "班主任": "teacher",
        "通用维度": "generic",
    }
    return mapping.get(job_type, "generic")

def required_dimensions_for_category(category: str) -> List[str]:
    """
    获取指定分类的必需维度列表
    Args:
        category: 策略分类
    Returns:
        必需维度名称列表
    """
    cat_info = COMPETENCY_CATEGORIES.get(category, COMPETENCY_CATEGORIES["通用维度"])
    return cat_info.get("required_dimensions", [])
def ensure_required_dimensions(dimensions: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    """
    确保维度列表包含必需维度
    Args:
        dimensions: 现有维度列表
        category: 策略分类
    Returns:
        包含必需维度的维度列表
    """
    required_names = required_dimensions_for_category(category)
    if not required_names:
        return dimensions
    # 获取现有维度名称
    existing_names = {dim.get("name", "") for dim in dimensions}
    # 添加缺失的必需维度
    result = list(dimensions)
    for req_name in required_names:
        if req_name not in existing_names:
            # 从模板中获取维度定义
            template = REQUIRED_DIMENSION_TEMPLATES.get(req_name)
            if template:
                result.append(deepcopy(template))
            else:
                # 如果没有模板,创建基础维度
                result.append({
                    "name": req_name,
                    "weight": 0.2,
                    "desc": f"{req_name}是岗位核心能力之一.",
                    "anchors": {
                        "20": "基础水平",
                        "60": "良好水平",
                        "100": "优秀水平",
                    }
                })
    return result
