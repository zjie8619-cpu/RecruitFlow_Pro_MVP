# ======================================================
# 🧠 ResumeAI 防幻觉与行业纠偏引擎（Final Ver.）
# 作者：ChatGPT 企业级优化版
# 功能：
#   - 避免 GPT 自动编造"竞赛获奖""教学经验"等虚假内容
#   - 根据岗位语义自动修正输出结果
#   - 支持所有行业（销售/运营/教育/技术/行政等）
# ======================================================

import re

# 导入统一的防幻觉函数
from backend.utils.sanitize import sanitize_ai_output as _sanitize_ai_output

# 🚧 定义行业关键字（语义识别层）
JOB_DOMAINS = {
    "销售": ["销售", "顾问", "电销", "邀约", "转化", "商务", "客户", "课程"],
    "运营": ["运营", "推广", "策划", "新媒体", "小红书", "抖音", "公众号"],
    "教育": ["教学", "讲师", "教师", "辅导", "学员", "课程设计", "培训师"],
    "技术": ["开发", "工程师", "测试", "系统", "算法", "代码"],
    "行政": ["行政", "人事", "档案", "绩效", "考勤"]
}

# 🚫 明确禁止出现在非教育类简历的短语
FORBIDDEN_EDU_PHRASES = [
    "竞赛", "比赛", "获奖", "辅导", "教学", "授课", "学生", "课堂", "讲解", "教育背景", "教师资格"
]

# 🚫 明确禁止出现在非学术类文本的幻觉模板
AI_HALLUCINATION_PATTERNS = [
    r"获得.{0,6}竞赛奖", r"拥有.{0,6}教学经验", r"指导.{0,6}学生", r"辅导.{0,6}比赛",
    r"参加.{0,6}竞赛", r"授课", r"教育行业背景", r"教师职业资格"
]

def clean_text(text: str) -> str:
    """统一文本格式"""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text

def detect_job_domain(job_title: str) -> str:
    """自动判断岗位类型"""
    for domain, keywords in JOB_DOMAINS.items():
        if any(k in job_title for k in keywords):
            return domain
    return "未知"

def sanitize_ai_output(ai_text: str, job_title: str) -> str:
    """
    🚀 主函数：防止幻觉内容出现在AI输出中（终极版）
    使用统一的防幻觉总控模块
    """
    return _sanitize_ai_output(ai_text, job_title)


# ---------------- 向后兼容函数（保留） -----------------
def clean_resume_text(text: str) -> str:
    """标准化、去噪（向后兼容）"""
    return clean_text(text)

def detect_industry(text: str, job_title: str = "") -> str:
    """识别行业方向并防止误判（向后兼容）"""
    domain = detect_job_domain(job_title)
    # 映射到旧版格式
    domain_map = {
        "销售": "销售类",
        "运营": "运营类",
        "教育": "教育类",
        "技术": "技术类",
        "行政": "行政/人事类",
        "未知": "未知"
    }
    return domain_map.get(domain, "未知")

def analyze_resume(resume_text: str, job_title: str, ai_generated_text: str = ""):
    """
    综合分析入口（向后兼容）：
    - 行业分类
    - 简历清洗
    - AI输出纠偏
    """
    clean_text_resume = clean_resume_text(resume_text)
    industry = detect_industry(clean_text_resume, job_title)
    safe_ai_text = sanitize_ai_output(ai_generated_text, job_title)

    return {
        "岗位": job_title,
        "行业识别": industry,
        "清洗后AI描述": safe_ai_text
    }

def analyze_resume_industry(resume_text: str, job_title: str):
    """
    通用简历分析：行业判断 + 清洗文本 + 行业匹配结果（向后兼容）
    """
    clean_text_resume = clean_resume_text(resume_text)
    industry = detect_industry(clean_text_resume, job_title)

    return {
        "岗位": job_title,
        "行业判断": industry,
        "文本样本": clean_text_resume[:200]  # 用于日志或调试预览
    }

def has_newmedia_experience(resume_text: str):
    """
    判断候选人是否具备真实的新媒体运营经验（向后兼容）
    """
    text = resume_text.lower()

    # 精准关键词
    newmedia_keywords = [
        "新媒体", "内容运营", "公众号", "抖音", "小红书", "知乎", "视频号",
        "短视频", "自媒体", "社群运营", "内容策划", "平台运营"
    ]

    # 操作动词：必须同时出现这些词才算真运营
    action_words = ["负责", "运营", "策划", "发布", "管理", "编辑", "搭建"]

    # 判断是否命中真实运营语义
    for kw in newmedia_keywords:
        for act in action_words:
            if re.search(rf"{act}.{{0,8}}{kw}", text) or re.search(rf"{kw}.{{0,8}}{act}", text):
                return True
    return False


# ---------------- 测试区 -----------------
if __name__ == "__main__":
    print("=" * 70)
    print("🧪 ResumeAI 防幻觉与行业纠偏引擎测试")
    print("=" * 70)
    
    samples = [
        {
            "title": "课程顾问",
            "ai": "候选人具有扎实的数学竞赛背景与辅导经验，曾获得国家一等奖。"
        },
        {
            "title": "新媒体运营",
            "ai": "候选人具备课堂教学经验，获得教育竞赛奖项。"
        },
        {
            "title": "Python开发工程师",
            "ai": "候选人指导学生参加编程竞赛并获奖。"
        },
        {
            "title": "数学教师",
            "ai": "候选人具有扎实的数学竞赛背景与辅导经验，曾获得国家一等奖。"
        }
    ]
    
    for s in samples:
        domain = detect_job_domain(s["title"])
        cleaned = sanitize_ai_output(s["ai"], s["title"])
        print(f"\n📋 岗位: {s['title']} → 行业: {domain}")
        print(f"📝 原始输出: {s['ai']}")
        print(f"✅ 清理后: {cleaned}")
        print("-" * 70)
