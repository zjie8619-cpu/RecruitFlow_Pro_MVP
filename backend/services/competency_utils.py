# backend/services/competency_utils.py
"""
# 能力模型工具函数:用于根据岗位类型确定能力维度策略
"""
from typing import List, Tuple, Dict, Any, Literal
from copy import deepcopy
from backend.services.text_rules import infer_job_family
# 岗位分类到能力维度的映射
COMPETENCY_CATEGORIES = {
#     "销售": {
#         "required_dimensions": ["销售能力", "客户沟通", "目标达成", "团队协作", "学习适应"],
#         "fixed_dimensions": ["销售能力", "客户沟通", "目标达成", "团队协作", "学习适应"],
},
#     "竞赛教练": {
#         "required_dimensions": ["学科专业能力", "竞赛辅导能力", "教学能力", "学生管理", "教研能力"],
#         "fixed_dimensions": ["学科专业能力", "竞赛辅导能力", "教学能力", "学生管理", "教研能力"],
},
#     "教师": {
#         "required_dimensions": ["教学能力", "学科专业能力", "学生管理", "沟通能力", "持续学习"],
#         "fixed_dimensions": ["教学能力", "学科专业能力", "学生管理", "沟通能力", "持续学习"],
},
#     "班主任": {
#         "required_dimensions": ["学生管理", "沟通协调", "家校合作", "问题解决", "责任心"],
#         "fixed_dimensions": ["学生管理", "沟通协调", "家校合作", "问题解决", "责任心"],
},
#     "通用维度": {
"required_dimensions": [],
"fixed_dimensions": [],
},
}
# 必需维度模板
REQUIRED_DIMENSION_TEMPLATES: Dict[str, Dict[str, Any]] = {
#     "销售能力": {
#         "name": "销售能力",
"weight": 0.2,
#         "desc": "能够有效识别客户需求,运用销售技巧促成交易,达成销售目标.",
"anchors": {
#             "20": "在指导下完成基础销售动作,能够介绍产品和服务.",
#             "60": "能够独立开发客户,运用销售技巧促成交易,达成销售目标.",
#             "100": "具备优秀的销售能力,能够识别并把握商机,持续超额完成销售目标.",
}
},
#     "客户沟通": {
#         "name": "客户沟通",
"weight": 0.2,
#         "desc": "能够与客户建立良好关系,有效沟通,理解客户需求.",
"anchors": {
#             "20": "能够进行基本的客户沟通,表达清晰.",
#             "60": "能够与客户建立良好关系,有效沟通,理解客户需求.",
#             "100": "具备优秀的沟通能力,能够与各类客户建立深度信任关系.",
}
},
#     "教学能力": {
#         "name": "教学能力",
"weight": 0.25,
#         "desc": "能够设计并实施有效的教学方案,帮助学生掌握知识和技能.",
"anchors": {
#             "20": "能够按照既定教案完成基础教学任务.",
#             "60": "能够设计并实施有效的教学方案,帮助学生掌握知识和技能.",
#             "100": "具备优秀的教学能力,能够创新教学方法,显著提升学生学习效果.",
}
},
#     "学科专业能力": {
#         "name": "学科专业能力",
"weight": 0.25,
#         "desc": "具备扎实的学科专业知识,能够准确解答学生问题.",
"anchors": {
#             "20": "具备基础的学科知识,能够解答常见问题.",
#             "60": "具备扎实的学科专业知识,能够准确解答学生问题.",
#             "100": "具备深厚的学科专业能力,能够处理复杂问题,并指导学生深入研究.",
}
},
#     "竞赛辅导能力": {
#         "name": "竞赛辅导能力",
"weight": 0.25,
#         "desc": "能够指导学生参加学科竞赛,帮助学生取得优异成绩.",
"anchors": {
#             "20": "能够进行基础的竞赛知识讲解.",
#             "60": "能够指导学生参加学科竞赛,帮助学生取得优异成绩.",
#             "100": "具备优秀的竞赛辅导能力,能够培养出获奖学生,在竞赛领域有突出成就.",
}
},
#     "学生管理": {
#         "name": "学生管理",
"weight": 0.2,
#         "desc": "能够有效管理学生,维护良好的班级秩序,关注学生成长.",
"anchors": {
#             "20": "能够维持基本的班级秩序.",
#             "60": "能够有效管理学生,维护良好的班级秩序,关注学生成长.",
#             "100": "具备优秀的学生管理能力,能够营造积极的学习氛围,促进学生全面发展.",
}
},
#     "沟通协调": {
#         "name": "沟通协调",
"weight": 0.2,
#         "desc": "能够与各方有效沟通,协调资源,解决问题.",
"anchors": {
#             "20": "能够进行基本的沟通交流.",
#             "60": "能够与各方有效沟通,协调资源,解决问题.",
#             "100": "具备优秀的沟通协调能力,能够高效处理复杂问题,建立良好合作关系.",
}
},
#     "家校合作": {
#         "name": "家校合作",
"weight": 0.2,
#         "desc": "能够与家长建立良好关系,共同促进学生成长.",
"anchors": {
#             "20": "能够进行基本的家校沟通.",
#             "60": "能够与家长建立良好关系,共同促进学生成长.",
#             "100": "具备优秀的家校合作能力,能够建立深度信任关系,形成教育合力.",
}
},
#     "目标达成": {
#         "name": "目标达成",
"weight": 0.2,
#         "desc": "能够设定并达成工作目标,具备良好的执行力.",
"anchors": {
#             "20": "能够在指导下完成基础工作任务.",
#             "60": "能够设定并达成工作目标,具备良好的执行力.",
#             "100": "具备优秀的目标达成能力,能够持续超额完成目标,并驱动团队达成更高目标.",
}
},
#     "团队协作": {
#         "name": "团队协作",
"weight": 0.15,
#         "desc": "能够与团队成员有效协作,共同完成工作任务.",
"anchors": {
#             "20": "能够参与团队协作,完成分配的任务.",
#             "60": "能够与团队成员有效协作,共同完成工作任务.",
#             "100": "具备优秀的团队协作能力,能够主动承担团队责任,推动团队整体提升.",
}
},
#     "学习适应": {
#         "name": "学习适应",
"weight": 0.15,
#         "desc": "能够快速学习新知识,适应工作变化.",
"anchors": {
#             "20": "能够学习基础的新知识和技能.",
#             "60": "能够快速学习新知识,适应工作变化.",
#             "100": "具备优秀的学习适应能力,能够主动学习并快速掌握新技能,推动工作创新.",
}
},
#     "持续学习": {
#         "name": "持续学习",
"weight": 0.15,
#         "desc": "具备持续学习的意识和能力,不断提升专业水平.",
"anchors": {
#             "20": "能够学习基础的新知识和技能.",
#             "60": "具备持续学习的意识和能力,不断提升专业水平.",
#             "100": "具备优秀的持续学习能力,能够主动学习并快速掌握新技能,推动工作创新.",
}
},
#     "沟通能力": {
#         "name": "沟通能力",
"weight": 0.15,
#         "desc": "能够与他人有效沟通,表达清晰,理解他人需求.",
"anchors": {
#             "20": "能够进行基本的沟通交流.",
#             "60": "能够与他人有效沟通,表达清晰,理解他人需求.",
#             "100": "具备优秀的沟通能力,能够与各类人群建立深度信任关系,高效解决问题.",
}
},
#     "问题解决": {
#         "name": "问题解决",
"weight": 0.2,
#         "desc": "能够识别问题,分析原因,提出并实施解决方案.",
"anchors": {
#             "20": "能够在指导下解决基础问题.",
#             "60": "能够识别问题,分析原因,提出并实施解决方案.",
#             "100": "具备优秀的问题解决能力,能够快速识别并解决复杂问题,预防潜在风险.",
}
},
#     "责任心": {
#         "name": "责任心",
"weight": 0.15,
#         "desc": "对工作负责,能够主动承担责任,确保工作质量.",
"anchors": {
#             "20": "能够完成基本的工作任务.",
#             "60": "对工作负责,能够主动承担责任,确保工作质量.",
#             "100": "具备强烈的责任心,能够主动承担额外责任,确保工作高质量完成.",
}
},
#     "教研能力": {
#         "name": "教研能力",
"weight": 0.15,
#         "desc": "能够进行教学研究,改进教学方法,提升教学质量.",
"anchors": {
#             "20": "能够参与基础的教学研究活动.",
#             "60": "能够进行教学研究,改进教学方法,提升教学质量.",
#             "100": "具备优秀的教研能力,能够进行深度教学研究,形成可推广的教学成果.",
}
},
}
def determine_competency_strategy(job_title: str) -> Tuple[str, List[str]]:
"""
#     根据岗位名称确定能力维度策略
Args:
#         job_title: 岗位名称
Returns:
#         (strategy_category, fixed_dimensions) 元组
#         - strategy_category: 策略分类(如"销售"、"竞赛教练"、"教师"、"班主任"、"通用维度")
#         - fixed_dimensions: 固定能力维度列表
"""
if not job_title:
#         return "通用维度", []
job_lower = job_title.lower()
# 判断岗位类型
job_family = infer_job_family(job_title)
# 根据岗位类型和关键词确定策略
if job_family == "coach":
#         return "竞赛教练", COMPETENCY_CATEGORIES["竞赛教练"]["fixed_dimensions"]
elif job_family == "teacher":
# 进一步判断是否为班主任
#         if "班主任" in job_title or "班主" in job_title:
#             return "班主任", COMPETENCY_CATEGORIES["班主任"]["fixed_dimensions"]
else:
#             return "教师", COMPETENCY_CATEGORIES["教师"]["fixed_dimensions"]
elif job_family == "sales":
#         return "销售", COMPETENCY_CATEGORIES["销售"]["fixed_dimensions"]
else:
# 通用维度,不提供固定维度
#         return "通用维度", []
def strategy_to_clean_family(job_type: str) -> Literal["coach", "teacher", "sales", "engineer_dev", "generic"]:
"""
#     将策略分类转换为清理用的 job family
Args:
#         job_type: 策略分类(如"销售"、"竞赛教练"、"教师"等)
Returns:
#         job family 字符串
"""
mapping = {
#         "销售": "sales",
#         "竞赛教练": "coach",
#         "教师": "teacher",
#         "班主任": "teacher",
#         "通用维度": "generic",
}
return mapping.get(job_type, "generic")
def required_dimensions_for_category(category: str) -> List[str]:
"""
#     获取指定分类的必需维度列表
Args:
#         category: 策略分类
Returns:
#         必需维度名称列表
"""
#     cat_info = COMPETENCY_CATEGORIES.get(category, COMPETENCY_CATEGORIES["通用维度"])
return cat_info.get("required_dimensions", [])
def ensure_required_dimensions(dimensions: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
"""
#     确保维度列表包含必需维度
Args:
#         dimensions: 现有维度列表
#         category: 策略分类
Returns:
#         包含必需维度的维度列表
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
#                     "desc": f"{req_name}是岗位核心能力之一.",
"anchors": {
#                         "20": "基础水平",
#                         "60": "良好水平",
#                         "100": "优秀水平",
}
})
return result
