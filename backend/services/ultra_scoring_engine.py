"""
Ultra 版评分引擎 - 整合所有模块
"""

from typing import Dict, Any
from backend.services.scoring_graph import ScoringGraph, ScoringResult
from backend.services.field_generators import FieldGenerators
from backend.services.robust_parser import RobustParser


class UltraScoringEngine:
    """Ultra 版评分引擎"""
    
    def __init__(self, job_title: str, jd_text: str = ""):
        self.job_title = job_title
        self.jd_text = jd_text
        self.scoring_graph = ScoringGraph(job_title, jd_text)
        self.field_generators = FieldGenerators(job_title)
        self.parser = RobustParser()
    
    def score(self, resume_text: str) -> Dict[str, Any]:
        """
        执行完整评分流程并生成所有字段
        
        返回完整的评分结果字典
        """
        # 执行评分推理（S1-S9）
        scoring_result = self.scoring_graph.execute(resume_text)
        
        # 即使有错误，也尝试生成基本字段（避免回退到旧版本）
        has_error = bool(scoring_result.error_code)
        
        # 生成四个字段（Ultra版）
        try:
            ai_review = self.field_generators.generate_ai_review(
                scoring_result,
                scoring_result.detected_actions,
                scoring_result.evidence_chain,
                scoring_result.risks
            )
        except Exception as e:
            print(f"[WARNING] 生成ai_review失败: {str(e)}")
            ai_review = "【证据】\n简历信息不足，无法进行详细评估。\n\n【推理】\n建议进一步了解候选人的具体工作内容和成果。\n\n【结论】\n信息不足，建议进一步了解候选人情况。"
        
        try:
            highlight_tags = self.field_generators.generate_highlight_tags(
                scoring_result.detected_actions,
                scoring_result.evidence_chain
            )
            # 确保至少有5个标签
            if len(highlight_tags) < 5:
                default_tags = ["执行力", "服务意识", "沟通表达", "学习指导", "组织协调"]
                for tag in default_tags:
                    if tag not in highlight_tags:
                        highlight_tags.append(tag)
                        if len(highlight_tags) >= 5:
                            break
        except Exception as e:
            print(f"[WARNING] 生成highlight_tags失败: {str(e)}")
            highlight_tags = ["执行力", "服务意识", "沟通表达", "学习指导", "组织协调"]
        
        try:
            # Ultra S8: 生成短板简历（有价值的追问点）
            weak_points = self.field_generators.generate_ai_resume_summary(
                resume_text,
                scoring_result.detected_actions,
                scoring_result.evidence_chain
            )
        except Exception as e:
            print(f"[WARNING] 生成weak_points失败: {str(e)}")
            weak_points = ["简历信息不足，建议进一步了解候选人情况"]
        
        try:
            # 生成原始简历摘要（用于显示）
            ai_resume_summary = self.field_generators.generate_resume_summary_original(
                resume_text,
                scoring_result.detected_actions,
                scoring_result.evidence_chain
            )
        except Exception as e:
            print(f"[WARNING] 生成ai_resume_summary失败: {str(e)}")
            ai_resume_summary = "简历信息不足，无法生成详细摘要"
        
        try:
            # 生成Ultra格式的summary_short（三行结构化）
            summary_short = self.field_generators.generate_summary_short(
                resume_text,
                scoring_result.detected_actions,
                highlight_tags,
                scoring_result.evidence_chain
            )
        except Exception as e:
            print(f"[WARNING] 生成summary_short失败: {str(e)}")
            summary_short = ai_resume_summary
        
        try:
            # Ultra S5: 生成证据链（去重+聚类+排版）
            evidence_text = self.field_generators.generate_evidence_text(
                scoring_result.evidence_chain
            )
        except Exception as e:
            print(f"[WARNING] 生成evidence_text失败: {str(e)}")
            evidence_text = "暂无有效证据"
        
        # 构建证据链字典（Ultra-Format）
        evidence_chains = {}
        dimension_order = ["技能匹配度", "经验相关性", "成长潜力", "稳定性"]
        for dim in dimension_order:
            dim_evidences = [
                {
                    "action": ev.action,
                    "evidence": ev.resume_quote,
                    "reasoning": ev.reasoning
                }
                for ev in scoring_result.evidence_chain
                if ev.dimension == dim
            ][:3]  # 每个维度最多3条
            if dim_evidences:
                evidence_chains[dim] = dim_evidences
        
        # 构建最终输出（Ultra-Format规范）
        result = {
            # Ultra-Format标准字段
            "ai_evaluation": ai_review,
            "highlights": highlight_tags,
            "summary_short": summary_short,  # 新增：三行结构化摘要
            "weak_points": weak_points,
            "evidence_chains": evidence_chains,
            "score_dims": {  # 雷达图数据（标准化字段名）
                "skill_match": round(scoring_result.skill_match_score / 25.0 * 100.0, 1),
                "experience_match": round(scoring_result.experience_match_score / 25.0 * 100.0, 1),
                "stability": round(scoring_result.stability_score / 25.0 * 100.0, 1),
                "growth_potential": round(scoring_result.growth_potential_score / 25.0 * 100.0, 1),
            },
            "scores": {  # 兼容字段
                "total": scoring_result.final_score,
                "skill_match": round(scoring_result.skill_match_score / 25.0 * 100.0, 1),
                "experience_match": round(scoring_result.experience_match_score / 25.0 * 100.0, 1),
                "stability": round(scoring_result.stability_score / 25.0 * 100.0, 1),
                "growth_potential": round(scoring_result.growth_potential_score / 25.0 * 100.0, 1),
            },
            
            # 兼容字段（用于现有UI）
            "总分": scoring_result.final_score,
            "维度得分": {
                "技能匹配度": round(scoring_result.skill_match_score / 25.0 * 100.0, 1),
                "经验相关性": round(scoring_result.experience_match_score / 25.0 * 100.0, 1),
                "稳定性": round(scoring_result.stability_score / 25.0 * 100.0, 1),
                "成长潜力": round(scoring_result.growth_potential_score / 25.0 * 100.0, 1),
            },
            "score_detail": {
                "skill_match": {
                    "score": scoring_result.skill_match_score,
                    "evidence": [
                        {
                            "action": ev.action,
                            "resume_quote": ev.resume_quote,
                            "reason": ev.reasoning
                        }
                        for ev in scoring_result.evidence_chain
                        if ev.dimension == "技能匹配度"
                    ]
                },
                "experience_match": {
                    "score": scoring_result.experience_match_score,
                    "evidence": [
                        {
                            "action": ev.action,
                            "resume_quote": ev.resume_quote,
                            "reason": ev.reasoning
                        }
                        for ev in scoring_result.evidence_chain
                        if ev.dimension == "经验相关性"
                    ]
                },
                "stability": {
                    "score": scoring_result.stability_score,
                    "evidence": [
                        {
                            "action": ev.action,
                            "resume_quote": ev.resume_quote,
                            "reason": ev.reasoning
                        }
                        for ev in scoring_result.evidence_chain
                        if ev.dimension == "稳定性"
                    ]
                },
                "growth_potential": {
                    "score": scoring_result.growth_potential_score,
                    "evidence": [
                        {
                            "action": ev.action,
                            "resume_quote": ev.resume_quote,
                            "reason": ev.reasoning
                        }
                        for ev in scoring_result.evidence_chain
                        if ev.dimension == "成长潜力"
                    ]
                },
                "final_score": scoring_result.final_score,
            },
            
            # 四个Ultra字段（兼容字段）
            "ai_review": ai_review,
            "highlight_tags": highlight_tags,
            "ai_resume_summary": ai_resume_summary,
            "summary_short": summary_short,  # Ultra格式摘要
            "evidence_text": evidence_text,
            "weak_points": weak_points,  # 新增：短板简历
            
            # 风险
            "risks": [
                {
                    "risk_type": risk.risk_type,
                    "evidence": risk.evidence,
                    "reason": risk.reason
                }
                for risk in scoring_result.risks
            ],
            
            # 匹配度
            "match_level": scoring_result.match_level,
            "match_summary": scoring_result.match_level,
            
            # 可解释性
            "score_explanation": scoring_result.score_explanation,
            
            # 元数据
            "detected_actions_count": len(scoring_result.detected_actions),
            "evidence_count": len(scoring_result.evidence_chain),
        }
        
        return result
    
    def _build_error_response(self, scoring_result: ScoringResult) -> Dict[str, Any]:
        """构建错误响应"""
        error_message = self.parser.format_error_message(
            scoring_result.error_code or "UNKNOWN_ERROR",
            scoring_result.error_message or "未知错误"
        )
        
        # 即使有错误，也尝试生成基本字段
        # 使用已有的detected_actions和evidence_chain（如果有）
        detected_actions = scoring_result.detected_actions or []
        evidence_chain = scoring_result.evidence_chain or []
        
        # 尝试生成基本字段
        try:
            if len(detected_actions) > 0:
                highlight_tags = self.field_generators.generate_highlight_tags(detected_actions, evidence_chain)
            else:
                highlight_tags = ["执行力", "服务意识", "沟通表达", "学习指导", "组织协调"]
        except:
            highlight_tags = ["执行力", "服务意识", "沟通表达", "学习指导", "组织协调"]
        
        # 生成基本的AI评价（即使有错误）
        if scoring_result.error_code == "INSUFFICIENT_ACTIONS":
            ai_review = "【证据】\n简历信息不足，检测到的有效动作过少，无法进行详细评估。\n\n【推理】\n建议进一步了解候选人的具体工作内容和成果。\n\n【结论】\n信息不足，建议进一步了解候选人情况。"
        else:
            ai_review = f"【证据】\n{error_message}\n\n【推理】\n系统无法完成完整评估，可能存在数据质量问题。\n\n【结论】\n无法评估，建议人工审核。"
        
        return {
            "总分": scoring_result.final_score or 0,
            "维度得分": {
                "技能匹配度": round(scoring_result.skill_match_score / 25.0 * 100.0, 1) if scoring_result.skill_match_score > 0 else 0,
                "经验相关性": round(scoring_result.experience_match_score / 25.0 * 100.0, 1) if scoring_result.experience_match_score > 0 else 0,
                "稳定性": round(scoring_result.stability_score / 25.0 * 100.0, 1) if scoring_result.stability_score > 0 else 0,
                "成长潜力": round(scoring_result.growth_potential_score / 25.0 * 100.0, 1) if scoring_result.growth_potential_score > 0 else 0,
            },
            "ai_evaluation": ai_review,
            "ai_review": ai_review,
            "highlight_tags": highlight_tags,
            "highlights": highlight_tags,  # 兼容字段
            "ai_resume_summary": "简历信息不足，无法生成详细摘要",
            "summary_short": "简历信息不足，无法生成详细摘要",
            "evidence_text": "暂无有效证据",
            "evidence_chains": {},
            "weak_points": ["简历信息不足，建议进一步了解候选人情况"],
            "risks": [{"risk_type": "信息不足", "evidence": error_message, "reason": "无法完成完整评估"}],
            "match_level": "无法评估",
            "match_summary": error_message,
            "error_code": scoring_result.error_code,
            "error_message": error_message,
            "score_dims": {
                "skill_match": round(scoring_result.skill_match_score / 25.0 * 100.0, 1) if scoring_result.skill_match_score > 0 else 0,
                "experience_match": round(scoring_result.experience_match_score / 25.0 * 100.0, 1) if scoring_result.experience_match_score > 0 else 0,
                "stability": round(scoring_result.stability_score / 25.0 * 100.0, 1) if scoring_result.stability_score > 0 else 0,
                "growth_potential": round(scoring_result.growth_potential_score / 25.0 * 100.0, 1) if scoring_result.growth_potential_score > 0 else 0,
            },
        }

