"""
Ultra-Format JSON 验证器
确保所有输出符合 Ultra-Format 规范
"""

from typing import Dict, Any, List, Tuple, Optional


class UltraFormatValidator:
    """Ultra-Format 验证器"""
    
    REQUIRED_FIELDS = {
        "score_detail": dict,
        "persona_tags": list,  # 或 highlight_tags
        "strengths_reasoning_chain": dict,
        "weaknesses_reasoning_chain": dict,
        "resume_mini": str,
        "match_summary": str,
        "risks": list,
    }
    
    SCORE_DETAIL_REQUIRED = {
        "skill_match": dict,
        "experience_match": dict,
        "growth_potential": dict,
        "stability": dict,
        "final_score": (int, float),
    }
    
    REASONING_CHAIN_REQUIRED = {
        "strengths": {
            "conclusion": str,
            "detected_actions": list,
            "resume_evidence": list,
            "ai_reasoning": str,
        },
        "weaknesses": {
            "conclusion": str,
            "resume_gap": list,
            "compare_to_jd": str,
            "ai_reasoning": str,
        }
    }
    
    @staticmethod
    def validate(result: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        验证结果是否符合 Ultra-Format
        
        返回: (is_valid, error_messages)
        """
        errors = []
        
        # 检查必需字段
        for field, expected_type in UltraFormatValidator.REQUIRED_FIELDS.items():
            if field not in result:
                # 允许 persona_tags 和 highlight_tags 互替
                if field == "persona_tags":
                    if "highlight_tags" not in result:
                        errors.append(f"缺少必需字段: {field} 或 highlight_tags")
                else:
                    errors.append(f"缺少必需字段: {field}")
            else:
                actual_type = type(result[field])
                if not isinstance(result[field], expected_type):
                    errors.append(f"字段 {field} 类型错误: 期望 {expected_type.__name__}, 实际 {actual_type.__name__}")
        
        # 检查 score_detail
        if "score_detail" in result:
            score_detail = result["score_detail"]
            for field, expected_type in UltraFormatValidator.SCORE_DETAIL_REQUIRED.items():
                if field not in score_detail:
                    errors.append(f"score_detail 缺少字段: {field}")
                elif field == "final_score":
                    if not isinstance(score_detail[field], (int, float)):
                        errors.append(f"score_detail.final_score 类型错误: 期望数字, 实际 {type(score_detail[field]).__name__}")
                else:
                    if not isinstance(score_detail[field], dict):
                        errors.append(f"score_detail.{field} 类型错误: 期望 dict, 实际 {type(score_detail[field]).__name__}")
                    elif "score" not in score_detail[field] or "evidence" not in score_detail[field]:
                        errors.append(f"score_detail.{field} 缺少必需子字段: score 或 evidence")
        
        # 检查推理链
        if "strengths_reasoning_chain" in result:
            chain = result["strengths_reasoning_chain"]
            if isinstance(chain, dict):
                for field in ["conclusion", "detected_actions", "resume_evidence", "ai_reasoning"]:
                    if field not in chain:
                        errors.append(f"strengths_reasoning_chain 缺少字段: {field}")
        
        if "weaknesses_reasoning_chain" in result:
            chain = result["weaknesses_reasoning_chain"]
            if isinstance(chain, dict):
                for field in ["conclusion", "resume_gap", "compare_to_jd", "ai_reasoning"]:
                    if field not in chain:
                        errors.append(f"weaknesses_reasoning_chain 缺少字段: {field}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def fix(result: Dict[str, Any]) -> Dict[str, Any]:
        """
        自动修复常见问题
        """
        fixed = result.copy()
        
        # 修复 persona_tags / highlight_tags 互替
        if "persona_tags" not in fixed and "highlight_tags" in fixed:
            fixed["persona_tags"] = fixed["highlight_tags"]
        elif "highlight_tags" not in fixed and "persona_tags" in fixed:
            fixed["highlight_tags"] = fixed["persona_tags"]
        
        # 修复 resume_mini
        if "resume_mini" not in fixed:
            fixed["resume_mini"] = fixed.get("summary_short", "") or fixed.get("ai_resume_summary", "")
        
        # 修复 match_summary
        if "match_summary" not in fixed:
            fixed["match_summary"] = fixed.get("match_level", "无法评估")
        
        # 修复推理链（只有在完全缺失时才设置默认值，否则保留已有内容）
        # 重要：不要覆盖已有的推理链内容，即使内容不完整也要保留
        if "strengths_reasoning_chain" not in fixed:
            # 只有在字段完全不存在时才设置默认值
            fixed["strengths_reasoning_chain"] = {
                "conclusion": "具备岗位所需的基础能力",
                "detected_actions": [],
                "resume_evidence": [],
                "ai_reasoning": "基于评分结果，候选人具备一定的工作能力，建议进一步了解具体工作内容。"
            }
        elif not fixed["strengths_reasoning_chain"]:
            # 如果字段存在但为空（空字典、None等），才设置默认值
            fixed["strengths_reasoning_chain"] = {
                "conclusion": "具备岗位所需的基础能力",
                "detected_actions": [],
                "resume_evidence": [],
                "ai_reasoning": "基于评分结果，候选人具备一定的工作能力，建议进一步了解具体工作内容。"
            }
        # 如果字段存在且有内容（即使是空字符串），都保留原内容，不覆盖
        
        if "weaknesses_reasoning_chain" not in fixed:
            # 只有在字段完全不存在时才设置默认值
            fixed["weaknesses_reasoning_chain"] = {
                "conclusion": "存在一定不足",
                "resume_gap": ["建议进一步了解候选人的相关经验"],
                "compare_to_jd": "建议面试时重点考察相关能力",
                "ai_reasoning": "基于评分结果，候选人存在一定不足，建议进一步评估。"
            }
        elif not fixed["weaknesses_reasoning_chain"]:
            # 如果字段存在但为空（空字典、None等），才设置默认值
            fixed["weaknesses_reasoning_chain"] = {
                "conclusion": "存在一定不足",
                "resume_gap": ["建议进一步了解候选人的相关经验"],
                "compare_to_jd": "建议面试时重点考察相关能力",
                "ai_reasoning": "基于评分结果，候选人存在一定不足，建议进一步评估。"
            }
        # 如果字段存在且有内容（即使是空字符串），都保留原内容，不覆盖
        
        # 修复 risks（确保是列表）
        if "risks" not in fixed:
            fixed["risks"] = []
        elif not isinstance(fixed["risks"], list):
            fixed["risks"] = [fixed["risks"]] if fixed["risks"] else []
        
        return fixed



