"""
Ultra版 AI 匹配器 - 集成新的评分引擎
"""

from typing import Dict, Any
import pandas as pd

from backend.services.ultra_scoring_engine import UltraScoringEngine


def ai_score_one_ultra(jd_text: str, resume_text: str, job_title: str = "") -> Dict[str, Any]:
    """
    Ultra版评分函数
    
    使用新的标准化推理框架（S1-S9）和Ultra字段生成器
    """
    try:
        engine = UltraScoringEngine(job_title, jd_text)
        result = engine.score(resume_text)
        
        # 调试：检查是否有错误
        if result.get("error_code"):
            print(f"[DEBUG] Ultra引擎返回错误: {result.get('error_code')} - {result.get('error_message')}")
        
        # 调试：检查关键字段是否存在
        if not result.get("ai_review") and not result.get("ai_evaluation"):
            print(f"[DEBUG] Ultra引擎未生成ai_review或ai_evaluation")
        if not result.get("highlight_tags"):
            print(f"[DEBUG] Ultra引擎未生成highlight_tags")
        if not result.get("ai_resume_summary") and not result.get("summary_short"):
            print(f"[DEBUG] Ultra引擎未生成ai_resume_summary或summary_short")
        
        # 转换为兼容格式（确保字段映射正确）
        # 1. AI评价：优先使用 ai_review，其次 ai_evaluation
        ai_review_val = result.get("ai_review", "") or result.get("ai_evaluation", "")
        result["short_eval"] = ai_review_val
        
        # 2. 亮点标签：从 highlight_tags 列表转为字符串（用 | 分隔）
        highlight_tags_list = result.get("highlight_tags", [])
        if isinstance(highlight_tags_list, list) and highlight_tags_list:
            result["highlights"] = " | ".join([str(tag) for tag in highlight_tags_list if tag])
        else:
            # 回退到旧字段
            old_highlights = result.get("highlights", [])
            if isinstance(old_highlights, list):
                result["highlights"] = " | ".join([str(tag) for tag in old_highlights if tag])
            elif isinstance(old_highlights, str):
                result["highlights"] = old_highlights
            else:
                result["highlights"] = ""
        
        # 3. 简历摘要：优先使用 ai_resume_summary，其次 summary_short
        result["resume_mini"] = result.get("ai_resume_summary", "") or result.get("summary_short", "")
        
        # 4. 证据文本：直接使用 evidence_text
        result["证据"] = result.get("evidence_text", "")
        
        # 确保保留所有Ultra原始字段（用于前端直接读取）
        # 这些字段会被直接传递到DataFrame，前端可以优先使用
        
        # 调试：输出关键字段状态
        print(f"[DEBUG] Ultra字段状态: ai_review={bool(result.get('ai_review'))}, highlight_tags={len(result.get('highlight_tags', []))}, ai_resume_summary={bool(result.get('ai_resume_summary'))}")
        
        return result
    except Exception as e:
        # 记录异常信息
        import traceback
        print(f"[ERROR] Ultra引擎异常: {str(e)}")
        print(f"[ERROR] 异常堆栈: {traceback.format_exc()}")
        
        # 回退到旧版本
        from backend.services.ai_matcher import ai_score_one
        try:
            from backend.services.ai_client import get_client_and_cfg
            client, cfg = get_client_and_cfg()
            print(f"[DEBUG] 回退到旧版本ai_matcher")
            return ai_score_one(client, cfg, jd_text, resume_text, job_title)
        except Exception as e2:
            print(f"[ERROR] 旧版本也失败: {str(e2)}")
            # 最终回退
            return {
                "总分": 0,
                "维度得分": {"技能匹配度": 0, "经验相关性": 0, "成长潜力": 0, "稳定性": 0},
                "short_eval": f"评分失败：{str(e)}",
                "highlights": "",
                "resume_mini": "",
                "证据": "",
            }


def ai_match_resumes_df_ultra(jd_text: str, resumes_df: pd.DataFrame, job_title: str = "") -> pd.DataFrame:
    """
    Ultra版批量匹配
    
    使用新的评分引擎对DataFrame中的所有简历进行评分
    """
    if resumes_df is None or resumes_df.empty:
        return pd.DataFrame()
    
    scored_rows = []
    
    for _, row in resumes_df.iterrows():
        resume_text = str(row.get("resume_text", "") or row.get("text_raw", "") or "")
        
        if not resume_text.strip():
            continue
        
        # 使用Ultra引擎评分
        score_result = ai_score_one_ultra(jd_text, resume_text, job_title)
        
        # 合并到原始行数据（包含Ultra字段）
        enriched = row.to_dict()
        
        # 获取维度得分（用于兼容旧UI）
        dim_scores = score_result.get("维度得分", {})
        
        # 获取Ultra格式的score_dims（用于雷达图）
        score_dims = score_result.get("score_dims", {})
        if not score_dims:
            # 如果没有score_dims，从维度得分转换
            score_dims = {
                "skill_match": dim_scores.get("技能匹配度", 0),
                "experience_match": dim_scores.get("经验相关性", 0),
                "growth_potential": dim_scores.get("成长潜力", 0),
                "stability": dim_scores.get("稳定性", 0),
            }
        
        # 获取亮点标签（确保是列表格式）
        highlight_tags = score_result.get("highlight_tags", [])
        if not highlight_tags or not isinstance(highlight_tags, list):
            # 如果highlight_tags不存在，尝试从highlights字符串解析
            highlights_str = score_result.get("highlights", "")
            if isinstance(highlights_str, str) and highlights_str:
                highlight_tags = [tag.strip() for tag in highlights_str.split("|") if tag.strip()]
            else:
                highlight_tags = []
        
        # 获取短板简历（weak_points）
        weak_points = score_result.get("weak_points", [])
        if not isinstance(weak_points, list):
            weak_points = [weak_points] if weak_points else []
        
        # 获取风险项（risks）
        risks = score_result.get("risks", [])
        if not isinstance(risks, list):
            risks = [risks] if risks else []
        
        enriched.update({
            # 基础评分字段
            "总分": score_result.get("总分", 0),
            "技能匹配度": dim_scores.get("技能匹配度", 0),
            "经验相关性": dim_scores.get("经验相关性", 0),
            "成长潜力": dim_scores.get("成长潜力", 0),
            "稳定性": dim_scores.get("稳定性", 0),
            
            # 兼容字段（用于列表页显示）
            "short_eval": score_result.get("short_eval", ""),
            "highlights": score_result.get("highlights", ""),
            "resume_mini": score_result.get("resume_mini", ""),
            "证据": score_result.get("证据", ""),
            
            # Ultra原始字段（前端优先使用）
            "ai_evaluation": score_result.get("ai_evaluation", ""),
            "ai_review": score_result.get("ai_review", "") or score_result.get("ai_evaluation", ""),
            "highlight_tags": highlight_tags,  # 列表格式
            "summary_short": score_result.get("summary_short", ""),
            "ai_resume_summary": score_result.get("ai_resume_summary", "") or score_result.get("summary_short", ""),
            "evidence_chains": score_result.get("evidence_chains", {}),
            "evidence_text": score_result.get("evidence_text", ""),
            "weak_points": weak_points,  # 列表格式
            "score_dims": score_dims,  # 雷达图数据
            "risks": risks,  # 风险项列表
            "match_level": score_result.get("match_level", "无法评估"),
        })
        
        scored_rows.append(enriched)
    
    result = pd.DataFrame(scored_rows)
    
    # 按总分排序
    if "总分" in result.columns:
        result = result.sort_values(by="总分", ascending=False).reset_index(drop=True)
    
    return result

