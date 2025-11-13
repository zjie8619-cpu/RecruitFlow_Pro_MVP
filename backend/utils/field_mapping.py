"""
字段名汉化映射
"""
FIELD_MAPPING = {
    # 评分字段
    "skill_fit": "技能贴合度",
    "exp_relevance": "经验相关性",
    "stability": "稳定性",
    "growth": "成长性",
    "confidence": "置信度",
    "score_total": "总分",
    "blocked_by_threshold": "阈值拦截",
    "evidence": "证据链",
    "evidence_json": "证据链JSON",
    
    # 简历字段
    "name": "姓名",
    "email": "邮箱",
    "phone": "手机号",
    "edu": "学历",
    "companies": "公司",
    "years": "工作年限",
    "skills": "技能",
    "projects": "项目经验",
    "text_raw": "原始文本",
    "source": "来源",
    "created_at": "创建时间",
    
    # 其他
    "job": "岗位",
    "resume_id": "简历ID",
    "id": "ID"
}

def translate_field(field_name: str) -> str:
    """将英文字段名翻译为中文"""
    return FIELD_MAPPING.get(field_name, field_name)

def translate_dataframe_columns(df):
    """翻译DataFrame的列名"""
    if df is None or df.empty:
        return df
    df = df.copy()
    df.columns = [translate_field(col) for col in df.columns]
    return df

