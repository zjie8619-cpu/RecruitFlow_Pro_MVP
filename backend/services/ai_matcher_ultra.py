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
        import time
        import sys
        start_time = time.time()
        # 强制刷新输出，确保日志立即显示
        print(f"[DEBUG] >>> 开始Ultra引擎评分: job_title={job_title}, resume_length={len(resume_text)}", flush=True)
        sys.stdout.flush()
        
        engine = UltraScoringEngine(job_title, jd_text)
        result = engine.score(resume_text)
        
        elapsed_time = time.time() - start_time
        print(f"[DEBUG] >>> Ultra引擎评分完成，耗时: {elapsed_time:.2f}秒", flush=True)
        sys.stdout.flush()
        
        # 调试：输出原始结果的关键字段（强制刷新）
        import sys
        print(f"[DEBUG] >>> RAW ULTRA RESULT:", flush=True)
        print(f"  - error_code: {result.get('error_code')}", flush=True)
        print(f"  - 总分: {result.get('总分', 0)}", flush=True)
        print(f"  - ai_review存在: {bool(result.get('ai_review'))}", flush=True)
        print(f"  - highlight_tags数量: {len(result.get('highlight_tags', []))}", flush=True)
        print(f"  - evidence_chain数量: {len(result.get('evidence_chains', {}))}", flush=True)
        print(f"  - detected_actions_count: {result.get('detected_actions_count', 0)}", flush=True)
        sys.stdout.flush()
        
        # 调试：检查是否有错误
        if result.get("error_code"):
            print(f"[WARNING] Ultra引擎返回错误: {result.get('error_code')} - {result.get('error_message')}", flush=True)
            sys.stdout.flush()
        
        # 调试：检查关键字段是否存在
        if not result.get("ai_review") and not result.get("ai_evaluation"):
            print(f"[WARNING] Ultra引擎未生成ai_review或ai_evaluation", flush=True)
            sys.stdout.flush()
        if not result.get("highlight_tags"):
            print(f"[WARNING] Ultra引擎未生成highlight_tags", flush=True)
            sys.stdout.flush()
        if not result.get("ai_resume_summary") and not result.get("summary_short"):
            print(f"[WARNING] Ultra引擎未生成ai_resume_summary或summary_short", flush=True)
            sys.stdout.flush()
        
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
        
        # 确保Ultra-Format标准字段存在
        if "persona_tags" not in result:
            result["persona_tags"] = result.get("highlight_tags", [])
        if "strengths_reasoning_chain" not in result:
            result["strengths_reasoning_chain"] = {}
        if "weaknesses_reasoning_chain" not in result:
            result["weaknesses_reasoning_chain"] = {}
        if "resume_mini" not in result:
            result["resume_mini"] = result.get("summary_short", "") or result.get("ai_resume_summary", "")
        
        # 调试：输出关键字段状态
        strengths_chain = result.get('strengths_reasoning_chain', {})
        weaknesses_chain = result.get('weaknesses_reasoning_chain', {})
        print(f"[DEBUG] Ultra字段状态: ai_review={bool(result.get('ai_review'))}, highlight_tags={len(result.get('highlight_tags', []))}, persona_tags={len(result.get('persona_tags', []))}", flush=True)
        print(f"[DEBUG]   strengths_chain存在: {bool(strengths_chain)}, conclusion={strengths_chain.get('conclusion', 'N/A') if isinstance(strengths_chain, dict) else 'N/A'}, ai_reasoning长度={len(strengths_chain.get('ai_reasoning', '')) if isinstance(strengths_chain, dict) else 0}", flush=True)
        print(f"[DEBUG]   weaknesses_chain存在: {bool(weaknesses_chain)}, conclusion={weaknesses_chain.get('conclusion', 'N/A') if isinstance(weaknesses_chain, dict) else 'N/A'}, ai_reasoning长度={len(weaknesses_chain.get('ai_reasoning', '')) if isinstance(weaknesses_chain, dict) else 0}", flush=True)
        sys.stdout.flush()
        
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
    total_count = len(resumes_df)
    import sys
    print(f"[DEBUG] ========================================", flush=True)
    print(f"[DEBUG] ai_match_resumes_df_ultra: 开始批量匹配，共{total_count}份简历", flush=True)
    print(f"[DEBUG] ========================================", flush=True)
    sys.stdout.flush()
    
    for idx, (_, row) in enumerate(resumes_df.iterrows(), 1):
        resume_text = str(row.get("resume_text", "") or row.get("text_raw", "") or "")
        
        if not resume_text.strip():
            print(f"[DEBUG] 简历{idx}/{total_count}: 文本为空，跳过", flush=True)
            sys.stdout.flush()
            continue
        
        print(f"[DEBUG] --- 简历{idx}/{total_count}: 开始评分，文本长度={len(resume_text)} ---", flush=True)
        sys.stdout.flush()
        # 使用Ultra引擎评分
        score_result = ai_score_one_ultra(jd_text, resume_text, job_title)
        print(f"[DEBUG] --- 简历{idx}/{total_count}: 评分完成 ---", flush=True)
        print(f"[DEBUG]   ai_review={bool(score_result.get('ai_review'))}", flush=True)
        print(f"[DEBUG]   strengths_reasoning_chain: conclusion={score_result.get('strengths_reasoning_chain', {}).get('conclusion')}, ai_reasoning长度={len(score_result.get('strengths_reasoning_chain', {}).get('ai_reasoning', ''))}", flush=True)
        print(f"[DEBUG]   weaknesses_reasoning_chain: conclusion={score_result.get('weaknesses_reasoning_chain', {}).get('conclusion')}, ai_reasoning长度={len(score_result.get('weaknesses_reasoning_chain', {}).get('ai_reasoning', ''))}", flush=True)
        print(f"[DEBUG]   highlight_tags={len(score_result.get('highlight_tags', []))}", flush=True)
        print(f"[DEBUG]   evidence_chains={len(score_result.get('evidence_chains', {}))}", flush=True)
        sys.stdout.flush()
        
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
            "persona_tags": score_result.get("persona_tags", highlight_tags),  # Ultra-Format标准字段
            "summary_short": score_result.get("summary_short", ""),
            "ai_resume_summary": score_result.get("ai_resume_summary", "") or score_result.get("summary_short", ""),
            "resume_mini": score_result.get("resume_mini", "") or score_result.get("summary_short", "") or score_result.get("ai_resume_summary", ""),
            "evidence_chains": score_result.get("evidence_chains", {}),
            "evidence_text": score_result.get("evidence_text", ""),
            "weak_points": weak_points,  # 列表格式
            "score_dims": score_dims,  # 雷达图数据
            "standard_model": score_result.get("standard_model", {}),  # 岗位标准能力模型（用于雷达图对比）
            "risks": risks,  # 风险项列表
            "match_level": score_result.get("match_level", "无法评估"),
            "match_summary": score_result.get("match_summary", "") or score_result.get("match_level", "无法评估"),
            # Ultra-Format推理链（必须字段）
            "strengths_reasoning_chain": score_result.get("strengths_reasoning_chain", {}),
            "weaknesses_reasoning_chain": score_result.get("weaknesses_reasoning_chain", {}),
            # Ultra-Format score_detail
            "score_detail": score_result.get("score_detail", {}),
        })
        
        scored_rows.append(enriched)
    
    result = pd.DataFrame(scored_rows)
    import sys
    print(f"[DEBUG] ========================================", flush=True)
    print(f"[DEBUG] ai_match_resumes_df_ultra: 批量匹配完成，共处理{len(scored_rows)}份简历", flush=True)
    print(f"[DEBUG] ========================================", flush=True)
    sys.stdout.flush()
    
    # 按总分排序
    if "总分" in result.columns:
        result = result.sort_values(by="总分", ascending=False).reset_index(drop=True)
    
    # 检查结果字段
    if len(result) > 0:
        sample_row = result.iloc[0]
        print(f"[DEBUG] 结果样本检查:", flush=True)
        print(f"  - ai_review: {bool(sample_row.get('ai_review'))}", flush=True)
        print(f"  - highlight_tags: {len(sample_row.get('highlight_tags', []))}", flush=True)
        print(f"  - evidence_chains: {len(sample_row.get('evidence_chains', {}))}", flush=True)
        
        # 检查推理链字段
        strengths_chain = sample_row.get('strengths_reasoning_chain', {})
        weaknesses_chain = sample_row.get('weaknesses_reasoning_chain', {})
        print(f"  - strengths_reasoning_chain类型: {type(strengths_chain)}", flush=True)
        if isinstance(strengths_chain, dict):
            print(f"  - strengths_reasoning_chain.conclusion: {strengths_chain.get('conclusion', 'N/A')}", flush=True)
            print(f"  - strengths_reasoning_chain.ai_reasoning长度: {len(strengths_chain.get('ai_reasoning', ''))}", flush=True)
        elif isinstance(strengths_chain, str):
            print(f"  - strengths_reasoning_chain是字符串，长度: {len(strengths_chain)}", flush=True)
        else:
            print(f"  - strengths_reasoning_chain值: {strengths_chain}", flush=True)
        
        print(f"  - weaknesses_reasoning_chain类型: {type(weaknesses_chain)}", flush=True)
        if isinstance(weaknesses_chain, dict):
            print(f"  - weaknesses_reasoning_chain.conclusion: {weaknesses_chain.get('conclusion', 'N/A')}", flush=True)
            print(f"  - weaknesses_reasoning_chain.ai_reasoning长度: {len(weaknesses_chain.get('ai_reasoning', ''))}", flush=True)
        elif isinstance(weaknesses_chain, str):
            print(f"  - weaknesses_reasoning_chain是字符串，长度: {len(weaknesses_chain)}", flush=True)
        else:
            print(f"  - weaknesses_reasoning_chain值: {weaknesses_chain}", flush=True)
        
        sys.stdout.flush()
    
    return result

