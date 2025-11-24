"""
Ultra 版评分引擎 - 整合所有模块
"""

from typing import Dict, Any, List
from backend.services.scoring_graph import ScoringGraph, ScoringResult
from backend.services.field_generators import FieldGenerators
from backend.services.robust_parser import RobustParser
from backend.services.ultra_format_validator import UltraFormatValidator


class UltraScoringEngine:
    """Ultra 版评分引擎"""
    
    def __init__(self, job_title: str, jd_text: str = ""):
        self.job_title = job_title
        self.jd_text = jd_text
        self.scoring_graph = ScoringGraph(job_title, jd_text)
        self.field_generators = FieldGenerators(job_title, jd_text)
        self.parser = RobustParser()
    
    def score(self, resume_text: str) -> Dict[str, Any]:
        """
        执行完整评分流程并生成所有字段
        
        返回完整的评分结果字典
        """
        import sys
        print(f"[DEBUG] Ultra引擎.score() 开始: resume_length={len(resume_text)}", flush=True)
        sys.stdout.flush()
        
        # 执行评分推理（S1-S9）
        scoring_result = self.scoring_graph.execute(resume_text)
        
        print(f"[DEBUG] ScoringGraph.execute() 完成:", flush=True)
        print(f"  - error_code: {scoring_result.error_code}", flush=True)
        print(f"  - detected_actions数量: {len(scoring_result.detected_actions)}", flush=True)
        print(f"  - evidence_chain数量: {len(scoring_result.evidence_chain)}", flush=True)
        print(f"  - final_score: {scoring_result.final_score}", flush=True)
        sys.stdout.flush()
        
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
        import sys
        evidence_chains = {}
        dimension_order = ["技能匹配度", "经验相关性", "成长潜力", "稳定性"]
        print(f"[DEBUG] 构建evidence_chains: evidence_chain长度={len(scoring_result.evidence_chain)}", flush=True)
        sys.stdout.flush()
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
                print(f"[DEBUG]   - {dim}: {len(dim_evidences)}条证据", flush=True)
                sys.stdout.flush()
        
        print(f"[DEBUG] evidence_chains最终结果: {len(evidence_chains)}个维度有数据", flush=True)
        sys.stdout.flush()
        
        # 生成优势推理链（Ultra-Format）
        strengths_reasoning_chain = self._generate_strengths_reasoning_chain(
            scoring_result, evidence_chains
        )
        
        # 生成劣势推理链（Ultra-Format）
        weaknesses_reasoning_chain = self._generate_weaknesses_reasoning_chain(
            scoring_result, evidence_chains
        )
        
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
            "persona_tags": highlight_tags,  # Ultra-Format标准字段名
            "ai_resume_summary": ai_resume_summary,
            "summary_short": summary_short,  # Ultra格式摘要
            "evidence_text": evidence_text,
            "weak_points": weak_points,  # 新增：短板简历
            
            # Ultra-Format推理链（必须字段）
            "strengths_reasoning_chain": strengths_reasoning_chain,
            "weaknesses_reasoning_chain": weaknesses_reasoning_chain,
            
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
            "resume_mini": summary_short or ai_resume_summary,  # Ultra-Format字段
            
            # 可解释性
            "score_explanation": scoring_result.score_explanation,
            
            # 元数据
            "detected_actions_count": len(scoring_result.detected_actions),
            "evidence_count": len(scoring_result.evidence_chain),
        }
        
        # 验证并修复 Ultra-Format
        is_valid, errors = UltraFormatValidator.validate(result)
        if not is_valid:
            print(f"[WARNING] Ultra-Format 验证失败: {errors}")
            result = UltraFormatValidator.fix(result)
            # 重新验证
            is_valid, errors = UltraFormatValidator.validate(result)
            if not is_valid:
                print(f"[ERROR] Ultra-Format 修复后仍失败: {errors}")
            else:
                print(f"[INFO] Ultra-Format 已自动修复")
        
        return result
    
    def _generate_strengths_reasoning_chain(
        self,
        scoring_result: ScoringResult,
        evidence_chains: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        生成优势推理链（Ultra-Format）
        
        格式：
        {
            "conclusion": str,
            "detected_actions": [str],
            "resume_evidence": [str],
            "ai_reasoning": str
        }
        """
        # 从技能匹配度和经验相关性中提取优势
        skill_evidences = evidence_chains.get("技能匹配度", [])
        exp_evidences = evidence_chains.get("经验相关性", [])
        
        # 合并优势证据
        all_strength_evidences = (skill_evidences + exp_evidences)[:3]
        
        if not all_strength_evidences:
            # 如果没有证据，从检测到的动作中生成
            top_actions = scoring_result.detected_actions[:3]
            detected_actions = [a.action for a in top_actions]
            resume_evidence = [a.resume_quote for a in top_actions if a.resume_quote]
            
            return {
                "conclusion": "具备岗位所需的核心能力",
                "detected_actions": detected_actions,
                "resume_evidence": resume_evidence[:3],
                "ai_reasoning": f"从简历中识别出{len(detected_actions)}个关键动作，体现了与岗位要求相关的工作能力"
            }
        
        # 提取动作和证据
        detected_actions = [ev.get("action", "") for ev in all_strength_evidences if ev.get("action")]
        resume_evidence = [ev.get("evidence", "") for ev in all_strength_evidences if ev.get("evidence")]
        reasoning_parts = [ev.get("reasoning", "") for ev in all_strength_evidences if ev.get("reasoning")]
        
        # 生成结论
        if scoring_result.skill_match_score >= 20:
            conclusion = "核心技能与岗位要求高度匹配"
        elif scoring_result.experience_match_score >= 18:
            conclusion = "工作经验与岗位场景高度相关"
        else:
            conclusion = "具备岗位所需的基础能力"
        
        # 生成推理文本
        ai_reasoning = f"技能匹配度得分{scoring_result.skill_match_score}分，经验相关性得分{scoring_result.experience_match_score}分。"
        if reasoning_parts:
            ai_reasoning += " ".join(reasoning_parts[:2])
        
        return {
            "conclusion": conclusion,
            "detected_actions": detected_actions[:3],
            "resume_evidence": resume_evidence[:3],
            "ai_reasoning": ai_reasoning
        }
    
    def _generate_weaknesses_reasoning_chain(
        self,
        scoring_result: ScoringResult,
        evidence_chains: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        生成劣势推理链（Ultra-Format）
        
        格式：
        {
            "conclusion": str,
            "resume_gap": [str],
            "compare_to_jd": str,
            "ai_reasoning": str
        }
        """
        # 找出最低分维度
        scores = {
            "技能匹配度": scoring_result.skill_match_score,
            "经验相关性": scoring_result.experience_match_score,
            "成长潜力": scoring_result.growth_potential_score,
            "稳定性": scoring_result.stability_score,
        }
        
        lowest_dim = min(scores.items(), key=lambda x: x[1])[0]
        lowest_score = scores[lowest_dim]
        
        # 从最低分维度提取证据
        lowest_evidences = evidence_chains.get(lowest_dim, [])
        
        # 提取gap（缺失的能力或经验）
        resume_gap = []
        if lowest_dim == "技能匹配度":
            resume_gap.append("核心技能与岗位要求存在差距")
        elif lowest_dim == "经验相关性":
            resume_gap.append("工作经验与岗位场景匹配度不足")
        elif lowest_dim == "成长潜力":
            resume_gap.append("学习成长能力有待提升")
        else:
            resume_gap.append("工作稳定性存在风险")
        
        # 从证据中提取更多gap信息
        if lowest_evidences:
            for ev in lowest_evidences[:2]:
                if ev.get("reasoning"):
                    gap_text = ev.get("reasoning", "").replace("该动作体现了", "").replace("相关能力", "")
                    if gap_text and gap_text not in resume_gap:
                        resume_gap.append(gap_text)
        
        # 生成对比JD的文本
        compare_to_jd = f"岗位要求{lowest_dim}，但候选人该维度得分仅{lowest_score}分"
        
        # 生成推理文本
        ai_reasoning = f"{lowest_dim}得分较低（{lowest_score}分），"
        if lowest_score < 10:
            ai_reasoning += "与岗位要求存在较大差距，建议面试时重点考察相关能力。"
        elif lowest_score < 15:
            ai_reasoning += "存在一定不足，建议进一步了解候选人的相关经验。"
        else:
            ai_reasoning += "基本符合要求，但仍有提升空间。"
        
        # 生成结论
        if lowest_score < 10:
            conclusion = f"{lowest_dim}明显不足"
        elif lowest_score < 15:
            conclusion = f"{lowest_dim}存在不足"
        else:
            conclusion = f"{lowest_dim}有待提升"
        
        return {
            "conclusion": conclusion,
            "resume_gap": resume_gap[:3],
            "compare_to_jd": compare_to_jd,
            "ai_reasoning": ai_reasoning
        }
    
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
            "persona_tags": highlight_tags,  # Ultra-Format标准字段名
            "highlights": highlight_tags,  # 兼容字段
            "ai_resume_summary": "简历信息不足，无法生成详细摘要",
            "summary_short": "简历信息不足，无法生成详细摘要",
            "resume_mini": "简历信息不足，无法生成详细摘要",
            "evidence_text": "暂无有效证据",
            "evidence_chains": {},
            "weak_points": ["简历信息不足，建议进一步了解候选人情况"],
            "risks": [{"risk_type": "信息不足", "evidence": error_message, "reason": "无法完成完整评估"}],
            "match_level": "无法评估",
            "match_summary": error_message,
            "strengths_reasoning_chain": {
                "conclusion": "无法评估",
                "detected_actions": [],
                "resume_evidence": [],
                "ai_reasoning": error_message
            },
            "weaknesses_reasoning_chain": {
                "conclusion": "信息不足",
                "resume_gap": ["简历信息不足"],
                "compare_to_jd": "无法对比",
                "ai_reasoning": error_message
            },
            "error_code": scoring_result.error_code,
            "error_message": error_message,
            "score_dims": {
                "skill_match": round(scoring_result.skill_match_score / 25.0 * 100.0, 1) if scoring_result.skill_match_score > 0 else 0,
                "experience_match": round(scoring_result.experience_match_score / 25.0 * 100.0, 1) if scoring_result.experience_match_score > 0 else 0,
                "stability": round(scoring_result.stability_score / 25.0 * 100.0, 1) if scoring_result.stability_score > 0 else 0,
                "growth_potential": round(scoring_result.growth_potential_score / 25.0 * 100.0, 1) if scoring_result.growth_potential_score > 0 else 0,
            },
        }

