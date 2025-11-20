# ======================================================
# 🚫 AI输出防幻觉总控模块 (Final Stable Version)
# 功能:
#   - 从源头禁止AI编造教育竞赛类内容
#   - 对输出做严格检测与重写
#   - 支持SiliconFlow/Claude等任意生成模型
# ======================================================

import re

# ===============================
# 1️⃣ 生成前:系统提示词注入
# ===============================
SYSTEM_PROMPT = """
# 你是一名招聘AI助手.你的任务是根据简历内容,分析候选人和岗位的匹配程度.请严格遵守以下约束:
# - 禁止编造任何简历中不存在的信息.
# - 禁止生成或提及以下内容:数学竞赛、奥数、辅导学生、教学、授课、教育背景、获奖经历.
# - 除非简历明确提及,不得假设候选人有教学或竞赛经验.
# - 对销售、运营、顾问、行政、技术岗位,只能生成行业通用描述,如"沟通能力强""有客户管理经验".
"""

# ===============================
# 2️⃣ 输出后:清洗与重写逻辑
# ===============================

FORBIDDEN_WORDS = [
#     "竞赛", "比赛", "获奖", "辅导", "教学", "学生", "课堂", "讲解",
#     "授课", "教育背景", "教师", "教练", "培训学生", "奥数", "一等奖", "二等奖"
]

FORBIDDEN_PATTERNS = [
#     r"曾获.{0,10}(竞赛|比赛|奖项)",
#     r"获得.{0,10}(奖项|竞赛|奥数)",
#     r"辅导.{0,10}(学生|竞赛)",
#     r"具备.{0,10}(教学|授课)经验",
#     r"指导.{0,10}学生",
#     r"教育行业背景",
#     r"数学竞赛",
#     r"奥数"
]

# REWRITE_TEXT = "该候选人信息存在异常,请人工复核其履历要点."

def sanitize_ai_output(ai_text: str, job_title: str) -> str:
    """
#     🚀 防幻觉主函数(生成后执行)
    
    Args:
#         ai_text: AI生成的文本内容
#         job_title: 岗位名称
    
    Returns:
#         清理后的文本,仅在检测到明显幻觉时才替换为中性描述
    """
    if not ai_text:
        return ""

    text = ai_text.strip()
    
    # 如果已经是异常提示,直接返回(避免重复处理)
    if text == REWRITE_TEXT:
        return text

    # 判断是否为教育行业岗位(扩展关键词列表)
#     education_keywords = ["教师", "讲师", "辅导", "教育", "培训师", "教练", "数学", "语文", "英语", "学科", "班主任", "教研", "竞赛教练", "课程", "顾问", "课程顾问", "招生", "学管", "学业规划"]
    is_education_job = any(k in job_title for k in education_keywords)
    
    # 教育行业岗位:宽松处理,只去除明显不相关的销售词汇
    if is_education_job:
        # 如果已经是异常提示,直接替换为通用评价
#         if "存在异常" in text:
#             return "该候选人具备教育行业相关经验,请结合简历进一步评估."
        
        # 仅去除明显的销售/客服类词汇(与教育无关)
#         sales_forbidden = ["开发客户", "拉新", "转化", "邀约", "电销", "销售转化", "业绩目标"]
        for word in sales_forbidden:
            text = text.replace(word, "")
        text = re.sub(r"\s+", " ", text).strip()
        
        # 如果清理后为空,使用通用评价
        if not text or len(text.strip()) < 5:
            return "该候选人具备教育行业相关经验,请结合简历进一步评估."
        
        # 教育行业岗位永远不替换为异常提示,直接返回
        return text
    
    # 非教育岗位:仅检测明显的幻觉模式,不进行过度清洗
    original_text = text
    has_obvious_hallucination = False
    
    # 只检测明显的幻觉模式(竞赛获奖、教学经验等)
    obvious_patterns = [
#         r"曾获.{0,10}(数学竞赛|奥数|竞赛).{0,10}(奖项|获奖)",
#         r"获得.{0,10}(数学竞赛|奥数).{0,10}(奖项|获奖)",
#         r"辅导.{0,10}学生.{0,10}(获奖|竞赛)",
#         r"具备.{0,10}(数学竞赛|奥数).{0,10}背景",
    ]
    
    for pattern in obvious_patterns:
        if re.search(pattern, text):
            has_obvious_hallucination = True
            break
    
    # 只有在检测到明显的幻觉模式时才替换
    if has_obvious_hallucination:
        # 尝试清理明显的幻觉词汇,保留其他内容
        cleaned = text
        for pattern in obvious_patterns:
            cleaned = re.sub(pattern, "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        
        # 如果清理后还有足够的内容(> 20字符),保留清理后的文本
        if len(cleaned) > 20:
            return cleaned
        # 否则才替换为异常提示
        return REWRITE_TEXT
    
    # 没有明显幻觉,直接返回原始文本(不进行清洗)
    return text


# ===============================
# 3️⃣ 测试
# ===============================
if __name__ == "__main__":
    print("=" * 70)
#     print("🧪 AI输出防幻觉总控模块测试")
    print("=" * 70)
    
    examples = [
        {
#             "job": "课程顾问",
#             "ai": "候选人具备高水平数学竞赛背景和丰富培训经验,曾指导多名学生获奖."
        },
        {
#             "job": "销售经理",
#             "ai": "候选人获全国奥数二等奖,具有教师培训经验."
        },
        {
#             "job": "新媒体运营",
#             "ai": "候选人具备课堂教学经验,获得教育竞赛奖项."
        },
        {
#             "job": "Python开发工程师",
#             "ai": "候选人指导学生参加编程竞赛并获奖."
        },
        {
#             "job": "教师",
#             "ai": "候选人有教学经验,擅长辅导学生."
        }
    ]

    for ex in examples:
#         print(f"\n📋 岗位: {ex['job']}")
#         print(f"📝 原始输出: {ex['ai']}")
#         print(f"✅ 清理后: {sanitize_ai_output(ex['ai'], ex['job'])}")
        print("-" * 70)

    examples = [
        {
#             "job": "课程顾问",
#             "ai": "候选人具备高水平数学竞赛背景和丰富培训经验,曾指导多名学生获奖."
        },
        {
#             "job": "销售经理",
#             "ai": "候选人获全国奥数二等奖,具有教师培训经验."
        },
        {
#             "job": "新媒体运营",
#             "ai": "候选人具备课堂教学经验,获得教育竞赛奖项."
        },
        {
#             "job": "Python开发工程师",
#             "ai": "候选人指导学生参加编程竞赛并获奖."
        },
        {
#             "job": "教师",
#             "ai": "候选人有教学经验,擅长辅导学生."
        }
    ]

    for ex in examples:
#         print(f"\n📋 岗位: {ex['job']}")
#         print(f"📝 原始输出: {ex['ai']}")
#         print(f"✅ 清理后: {sanitize_ai_output(ex['ai'], ex['job'])}")
        print("-" * 70)
