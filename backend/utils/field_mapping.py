import pandas as pd
from typing import Dict

# 字段映射字典:英文 -> 中文
FIELD_MAPPING: Dict[str, str] = {
    # 候选人基本信息
#     "candidate_id": "候选人ID",
#     "file": "文件名",
#     "name": "姓名",
#     "email": "邮箱",
#     "phone": "电话",
#     "text_len": "文本长度",
#     "resume_text": "简历文本",

    # 评分相关
#     "score_total": "总分",
#     "总分": "总分",
#     "skill_fit": "技能匹配度",
#     "技能匹配度": "技能匹配度",
#     "exp_relevance": "经验相关性",
#     "经验相关性": "经验相关性",
#     "growth": "成长潜力",
#     "成长潜力": "成长潜力",
#     "stability": "稳定性",
#     "稳定性": "稳定性",
#     "score": "总分",
#     "match_score": "匹配分数",
#     "AI_score": "AI评分",

    # 评价相关
#     "short_eval": "AI评价",
#     "evidence": "证据",
#     "证据": "证据",
#     "简评": "简评",
#     "confidence": "置信度",

    # 其他字段
#     "rank": "排名",
#     "created_at": "创建时间",
#     "updated_at": "更新时间",
#     "job": "岗位",
#     "jd_long": "长版JD",
#     "jd_short": "短版JD",
#     "resume_id": "简历ID",
    "id": "ID",
#     "edu": "学历",
#     "companies": "公司",
#     "years": "工作年限",
#     "skills": "技能",
#     "projects": "项目经验",
#     "text_raw": "原始文本",
#     "source": "来源",
#     "blocked_by_threshold": "阈值拦截",
#     "evidence_json": "证据链JSON",
}

def translate_field(field_name: str) -> str:
    """翻译单个字段名"""
    return FIELD_MAPPING.get(field_name, field_name)

def translate_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
#     翻译 DataFrame 的列名
    """
    if df is None or df.empty:
        return df

    df_copy = df.copy()
    new_columns = {}

    for col in df_copy.columns:
        translated = translate_field(str(col))
        if translated != col:
            new_columns[col] = translated

    if new_columns:
        df_copy = df_copy.rename(columns=new_columns)

    return df_copy
