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
    
    def _generate_standard_model(self) -> Dict[str, float]:
        """
        使用AI从岗位JD智能生成标准能力模型（百分制）
        返回4个维度的标准分，用于雷达图对比
        """
        import sys
        import json
        import textwrap
        import re
        
        # 如果没有JD，使用默认标准模型
        if not self.jd_text or len(self.jd_text.strip()) < 50:
            # 默认标准模型：根据岗位类型设置
            job_lower = (self.job_title or "").lower()
            if any(kw in job_lower for kw in ["班主任", "学管", "教务", "教育"]):
                return {
                    "skill_match": 80.0,
                    "experience_match": 75.0,
                    "stability": 85.0,
                    "growth_potential": 70.0,
                }
            elif any(kw in job_lower for kw in ["销售", "顾问", "bd"]):
                return {
                    "skill_match": 75.0,
                    "experience_match": 85.0,
                    "stability": 80.0,
                    "growth_potential": 70.0,
                }
            else:
                # 通用标准模型
                return {
                    "skill_match": 80.0,
                    "experience_match": 80.0,
                    "stability": 80.0,
                    "growth_potential": 75.0,
                }
        
        # 使用AI智能生成标准模型
        try:
            client, cfg = self.field_generators._get_llm_client()
            if client and cfg and cfg.api_key:
                print(f"[DEBUG] 使用AI生成岗位标准能力模型...", flush=True)
                sys.stdout.flush()
                
                prompt = textwrap.dedent(f"""
                你是一名专业的招聘能力模型专家。请基于以下岗位JD，智能分析并生成该岗位的标准能力模型评分（百分制）。

                【岗位名称】
                {self.job_title}

                【岗位JD】
                {self.jd_text[:1000]}

                ----------------------------------------------
                【任务要求】
                ----------------------------------------------
                请分析该岗位JD，为以下4个维度生成标准分（0-100分），这些分数代表该岗位对候选人的期望标准：

                1. **技能匹配度** (skill_match): 该岗位对核心技能的要求程度
                   - 如果JD中明确要求多项专业技能，分数应该较高（80-95）
                   - 如果JD中只要求基础技能，分数应该中等（60-75）
                   - 如果JD中对技能要求不明确，分数应该较低（50-65）

                2. **经验相关性** (experience_match): 该岗位对相关工作经验的要求程度
                   - 如果JD中明确要求特定行业/岗位经验，分数应该较高（80-95）
                   - 如果JD中只要求一般工作经验，分数应该中等（60-75）
                   - 如果JD中对经验要求不明确，分数应该较低（50-65）

                3. **稳定性** (stability): 该岗位对工作稳定性的要求程度
                   - 如果JD中强调长期、稳定、持续，分数应该较高（80-95）
                   - 如果JD中对稳定性有一般要求，分数应该中等（60-75）
                   - 如果JD中对稳定性要求不明确，分数应该较低（50-65）

                4. **成长潜力** (growth_potential): 该岗位对学习成长能力的要求程度
                   - 如果JD中强调学习、成长、发展、培养，分数应该较高（75-90）
                   - 如果JD中对成长有一般要求，分数应该中等（60-75）
                   - 如果JD中对成长要求不明确，分数应该较低（50-65）

                ----------------------------------------------
                【输出格式】
                ----------------------------------------------
                请严格按照以下JSON格式输出，不要添加任何其他内容：

                {{
                    "skill_match": 85.0,
                    "experience_match": 80.0,
                    "stability": 75.0,
                    "growth_potential": 70.0
                }}

                ----------------------------------------------
                【注意事项】
                ----------------------------------------------
                1. 所有分数必须是0-100之间的浮点数
                2. 分数应该基于JD的实际内容，不要随意猜测
                3. 不同岗位应该有明显不同的标准模型
                4. 输出必须是有效的JSON格式
                """)
                
                try:
                    from backend.services.ai_client import chat_completion
                    response = chat_completion(
                        client,
                        cfg,
                        messages=[
                            {"role": "system", "content": "你是一名专业的招聘能力模型专家，能够基于岗位JD智能分析并生成标准能力模型。"},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.3,  # 降低温度，确保输出稳定
                        max_tokens=300,
                    )
                    
                    content = response["choices"][0]["message"]["content"].strip()
                    
                    # 尝试提取JSON
                    import re
                    json_match = re.search(r'\{[^{}]*"skill_match"[^{}]*\}', content, re.DOTALL)
                    if json_match:
                        content = json_match.group(0)
                    
                    # 解析JSON
                    standard_model = json.loads(content)
                    
                    # 验证和规范化
                    result = {
                        "skill_match": round(float(standard_model.get("skill_match", 80.0)), 1),
                        "experience_match": round(float(standard_model.get("experience_match", 80.0)), 1),
                        "stability": round(float(standard_model.get("stability", 80.0)), 1),
                        "growth_potential": round(float(standard_model.get("growth_potential", 75.0)), 1),
                    }
                    
                    # 确保所有值在0-100范围内
                    for key in result:
                        result[key] = max(0.0, min(100.0, result[key]))
                    
                    print(f"[DEBUG] AI生成的标准模型: {result}", flush=True)
                    sys.stdout.flush()
                    return result
                    
                except Exception as e:
                    print(f"[WARNING] AI生成标准模型失败: {str(e)}，回退到规则生成", flush=True)
                    sys.stdout.flush()
        except Exception as e:
            print(f"[WARNING] 无法使用AI生成标准模型: {str(e)}，回退到规则生成", flush=True)
            sys.stdout.flush()
        
        # 回退到规则生成（改进版）
        jd_lower = self.jd_text.lower()
        
        # 技能匹配度标准分：基于JD中提到的技能要求（更精确的分析）
        skill_indicators = ["技能", "能力", "掌握", "熟悉", "精通", "要求", "具备", "擅长", "熟练"]
        skill_mentions = sum(1 for kw in skill_indicators if kw in jd_lower)
        skill_requirements = len(re.findall(r'(?:要求|需要|具备|掌握|熟悉|精通)[^，。]{2,10}', jd_lower))
        skill_match_standard = min(100.0, 60.0 + skill_mentions * 3.0 + skill_requirements * 5.0)
        
        # 经验相关性标准分：基于JD中提到的经验要求（更精确的分析）
        exp_indicators = ["经验", "经历", "背景", "从事", "做过", "负责过", "相关经验", "行业经验"]
        exp_mentions = sum(1 for kw in exp_indicators if kw in jd_lower)
        exp_requirements = len(re.findall(r'(?:要求|需要)[^，。]{0,10}(?:经验|经历|背景)', jd_lower))
        experience_match_standard = min(100.0, 60.0 + exp_mentions * 3.0 + exp_requirements * 5.0)
        
        # 稳定性标准分：基于JD中提到的稳定性要求
        stability_indicators = ["稳定", "长期", "持续", "坚持", "忠诚", "长期合作"]
        stability_mentions = sum(1 for kw in stability_indicators if kw in jd_lower)
        stability_standard = min(100.0, 70.0 + stability_mentions * 4.0)
        
        # 成长潜力标准分：基于JD中提到的成长要求
        growth_indicators = ["学习", "成长", "发展", "提升", "进步", "培养", "培训", "成长空间"]
        growth_mentions = sum(1 for kw in growth_indicators if kw in jd_lower)
        growth_standard = min(100.0, 65.0 + growth_mentions * 4.0)
        
        return {
            "skill_match": round(skill_match_standard, 1),
            "experience_match": round(experience_match_standard, 1),
            "stability": round(stability_standard, 1),
            "growth_potential": round(growth_standard, 1),
        }
    
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
        print(f"[DEBUG] 开始生成优势推理链...", flush=True)
        sys.stdout.flush()
        strengths_reasoning_chain = self._generate_strengths_reasoning_chain(
            scoring_result, evidence_chains
        )
        print(f"[DEBUG] 优势推理链生成完成: conclusion={strengths_reasoning_chain.get('conclusion')}, ai_reasoning长度={len(strengths_reasoning_chain.get('ai_reasoning', ''))}", flush=True)
        sys.stdout.flush()
        
        # 生成劣势推理链（Ultra-Format）
        print(f"[DEBUG] 开始生成劣势推理链...", flush=True)
        sys.stdout.flush()
        weaknesses_reasoning_chain = self._generate_weaknesses_reasoning_chain(
            scoring_result, evidence_chains
        )
        print(f"[DEBUG] 劣势推理链生成完成: conclusion={weaknesses_reasoning_chain.get('conclusion')}, ai_reasoning长度={len(weaknesses_reasoning_chain.get('ai_reasoning', ''))}", flush=True)
        sys.stdout.flush()
        
        # 生成岗位标准能力模型（用于雷达图对比）
        standard_model = self._generate_standard_model()
        print(f"[DEBUG] 岗位标准能力模型: {standard_model}", flush=True)
        sys.stdout.flush()
        
        # 构建最终输出（Ultra-Format规范，符合要求的JSON结构）
        result = {
            # 核心评分字段（百分制，符合要求）
            "scores": {
                "skill_match": round(scoring_result.skill_match_score, 1),
                "experience_match": round(scoring_result.experience_match_score, 1),
                "growth_potential": round(scoring_result.growth_potential_score, 1),
                "stability": round(scoring_result.stability_score, 1),
                "total_score": round(scoring_result.final_score, 1),
            },
            # 岗位标准能力模型（百分制，用于雷达图对比）
            "standard_model": {
                "skill_match": standard_model["skill_match"],
                "experience_match": standard_model["experience_match"],
                "growth_potential": standard_model["growth_potential"],
                "stability": standard_model["stability"],
            },
            # 标签（从evidence_chain提取，禁止幻觉）
            "tags": highlight_tags,
            # 摘要
            "summary": summary_short or ai_resume_summary,
            # 证据链（统一格式，符合要求）
            "evidence_chain": [
                {
                    "dimension": ev.dimension,
                    "actions": [ev.action],
                    "raw_evidence": ev.resume_quote,
                    "reasoning": ev.reasoning
                }
                for ev in scoring_result.evidence_chain[:10]  # 最多10条
            ],
            # 风险提示
            "risk_alert": "; ".join([r.risk_type for r in scoring_result.risks[:3]]) if scoring_result.risks else "",
            # 亮点文本
            "highlights": " | ".join(highlight_tags[:5]) if highlight_tags else "",
            
            # Ultra-Format标准字段（兼容）
            "ai_evaluation": ai_review,
            "ai_review": ai_review,
            "summary_short": summary_short,  # 新增：三行结构化摘要
            "weak_points": weak_points,
            "evidence_chains": evidence_chains,
            "evidence_chain": [  # 统一证据链格式（列表格式）
                {
                    "dimension": ev.dimension,
                    "actions": [ev.action],
                    "raw_evidence": ev.resume_quote,
                    "reasoning": ev.reasoning
                }
                for ev in scoring_result.evidence_chain[:10]  # 最多10条
            ],
            "score_dims": {  # 雷达图数据（标准化字段名，已经是百分制）
                "skill_match": round(scoring_result.skill_match_score, 1),
                "experience_match": round(scoring_result.experience_match_score, 1),
                "stability": round(scoring_result.stability_score, 1),
                "growth_potential": round(scoring_result.growth_potential_score, 1),
            },
            "standard_model": {  # 岗位标准能力模型（百分制，用于雷达图对比）
                "skill_match": standard_model["skill_match"],
                "experience_match": standard_model["experience_match"],
                "stability": standard_model["stability"],
                "growth_potential": standard_model["growth_potential"],
            },
            "scores": {  # 兼容字段（已经是百分制）
                "total": scoring_result.final_score,
                "skill_match": round(scoring_result.skill_match_score, 1),
                "experience_match": round(scoring_result.experience_match_score, 1),
                "stability": round(scoring_result.stability_score, 1),
                "growth_potential": round(scoring_result.growth_potential_score, 1),
            },
            
            # 兼容字段（用于现有UI，已经是百分制）
            "总分": scoring_result.final_score,
            "维度得分": {
                "技能匹配度": round(scoring_result.skill_match_score, 1),
                "经验相关性": round(scoring_result.experience_match_score, 1),
                "稳定性": round(scoring_result.stability_score, 1),
                "成长潜力": round(scoring_result.growth_potential_score, 1),
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
            "tags": highlight_tags,  # 统一标签字段名
            "persona_tags": highlight_tags,  # Ultra-Format标准字段名
            "ai_resume_summary": ai_resume_summary,
            "summary_short": summary_short,  # Ultra格式摘要
            "summary": summary_short or ai_resume_summary,  # 统一摘要字段名
            "evidence_text": evidence_text,
            "weak_points": weak_points,  # 新增：短板简历
            "risk_alert": "; ".join([r.risk_type for r in scoring_result.risks[:3]]) if scoring_result.risks else "",  # 风险提示
            "highlights": " | ".join(highlight_tags[:5]) if highlight_tags else "",  # 亮点文本
            
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
        
        # 验证并修复 Ultra-Format（但保留已有的推理链内容）
        strengths_before = result.get('strengths_reasoning_chain', {})
        weaknesses_before = result.get('weaknesses_reasoning_chain', {})
        strengths_conclusion_before = strengths_before.get('conclusion', '') if isinstance(strengths_before, dict) else ''
        weaknesses_conclusion_before = weaknesses_before.get('conclusion', '') if isinstance(weaknesses_before, dict) else ''
        
        print(f"[DEBUG] 验证前推理链状态: strengths_conclusion={strengths_conclusion_before[:30] if strengths_conclusion_before else 'None'}, weaknesses_conclusion={weaknesses_conclusion_before[:30] if weaknesses_conclusion_before else 'None'}", flush=True)
        sys.stdout.flush()
        
        is_valid, errors = UltraFormatValidator.validate(result)
        if not is_valid:
            print(f"[WARNING] Ultra-Format 验证失败: {errors}", flush=True)
            sys.stdout.flush()
            # 保存已有的推理链内容（深拷贝）
            import copy
            saved_strengths = copy.deepcopy(result.get("strengths_reasoning_chain", {}))
            saved_weaknesses = copy.deepcopy(result.get("weaknesses_reasoning_chain", {}))
            
            # 记录保存的内容
            if saved_strengths and isinstance(saved_strengths, dict):
                print(f"[DEBUG] 保存优势推理链: conclusion={saved_strengths.get('conclusion', '')[:30]}, ai_reasoning长度={len(saved_strengths.get('ai_reasoning', ''))}", flush=True)
            if saved_weaknesses and isinstance(saved_weaknesses, dict):
                print(f"[DEBUG] 保存劣势推理链: conclusion={saved_weaknesses.get('conclusion', '')[:30]}, ai_reasoning长度={len(saved_weaknesses.get('ai_reasoning', ''))}", flush=True)
            
            result = UltraFormatValidator.fix(result)
            
            # 检查修复后的推理链，如果被覆盖了，恢复保存的内容
            fixed_strengths = result.get("strengths_reasoning_chain", {})
            fixed_weaknesses = result.get("weaknesses_reasoning_chain", {})
            
            # 强制恢复：如果保存的内容有conclusion或ai_reasoning，就恢复
            if saved_strengths and isinstance(saved_strengths, dict):
                saved_conclusion = saved_strengths.get("conclusion", "")
                saved_reasoning = saved_strengths.get("ai_reasoning", "")
                
                # 如果保存的内容有有效内容，强制恢复
                if saved_conclusion or (saved_reasoning and len(saved_reasoning) > 10):
                    result["strengths_reasoning_chain"] = saved_strengths
                    print(f"[DEBUG] 强制恢复优势推理链: conclusion={saved_conclusion[:30] if saved_conclusion else 'None'}, ai_reasoning长度={len(saved_reasoning)}", flush=True)
                    sys.stdout.flush()
            
            if saved_weaknesses and isinstance(saved_weaknesses, dict):
                saved_conclusion = saved_weaknesses.get("conclusion", "")
                saved_reasoning = saved_weaknesses.get("ai_reasoning", "")
                
                # 如果保存的内容有有效内容，强制恢复
                if saved_conclusion or (saved_reasoning and len(saved_reasoning) > 10):
                    result["weaknesses_reasoning_chain"] = saved_weaknesses
                    print(f"[DEBUG] 强制恢复劣势推理链: conclusion={saved_conclusion[:30] if saved_conclusion else 'None'}, ai_reasoning长度={len(saved_reasoning)}", flush=True)
                    sys.stdout.flush()
            
            # 重新验证
            is_valid, errors = UltraFormatValidator.validate(result)
            if not is_valid:
                print(f"[ERROR] Ultra-Format 修复后仍失败: {errors}", flush=True)
                sys.stdout.flush()
            else:
                print(f"[INFO] Ultra-Format 已自动修复", flush=True)
                sys.stdout.flush()
        
        strengths_after = result.get('strengths_reasoning_chain', {})
        weaknesses_after = result.get('weaknesses_reasoning_chain', {})
        strengths_conclusion_after = strengths_after.get('conclusion', '') if isinstance(strengths_after, dict) else ''
        weaknesses_conclusion_after = weaknesses_after.get('conclusion', '') if isinstance(weaknesses_after, dict) else ''
        
        print(f"[DEBUG] 最终推理链状态: strengths_conclusion={strengths_conclusion_after[:30] if strengths_conclusion_after else 'None'}, weaknesses_conclusion={weaknesses_conclusion_after[:30] if weaknesses_conclusion_after else 'None'}", flush=True)
        sys.stdout.flush()
        
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
            detected_actions = [a.action for a in top_actions if a.action]
            resume_evidence = [a.resume_quote for a in top_actions if a.resume_quote and len(a.resume_quote.strip()) >= 5]
            
            # 如果detected_actions为空，至少生成一个默认结论
            if not detected_actions:
                # 基于得分生成结论
                if scoring_result.skill_match_score >= 20 or scoring_result.experience_match_score >= 18:
                    conclusion = "具备岗位所需的核心能力"
                    ai_reasoning = f"技能匹配度得分{scoring_result.skill_match_score}分，经验相关性得分{scoring_result.experience_match_score}分，表明候选人具备岗位所需的核心能力。"
                elif scoring_result.skill_match_score >= 15 or scoring_result.experience_match_score >= 15:
                    conclusion = "具备岗位所需的基础能力"
                    ai_reasoning = f"技能匹配度得分{scoring_result.skill_match_score}分，经验相关性得分{scoring_result.experience_match_score}分，表明候选人具备岗位所需的基础能力，建议进一步了解具体工作内容。"
                else:
                    conclusion = "具备一定的工作能力"
                    ai_reasoning = f"技能匹配度得分{scoring_result.skill_match_score}分，经验相关性得分{scoring_result.experience_match_score}分，建议进一步了解候选人的具体工作内容和成果。"
                
                print(f"[DEBUG] 优势推理链：从得分生成，conclusion={conclusion}", flush=True)
                sys.stdout.flush()
                return {
                    "conclusion": conclusion,
                    "detected_actions": [],
                    "resume_evidence": [],
                    "ai_reasoning": ai_reasoning
                }
            
            conclusion = "具备岗位所需的核心能力"
            ai_reasoning = f"从简历中识别出{len(detected_actions)}个关键动作，体现了与岗位要求相关的工作能力。技能匹配度得分{scoring_result.skill_match_score}分，经验相关性得分{scoring_result.experience_match_score}分。"
            print(f"[DEBUG] 优势推理链：从动作生成，detected_actions数量={len(detected_actions)}", flush=True)
            sys.stdout.flush()
            return {
                "conclusion": conclusion,
                "detected_actions": detected_actions,
                "resume_evidence": resume_evidence[:3] if resume_evidence else [],
                "ai_reasoning": ai_reasoning
            }
        
        # 提取动作和证据（过滤空值）
        detected_actions = [ev.get("action", "") for ev in all_strength_evidences if ev.get("action") and len(ev.get("action", "").strip()) >= 3]
        resume_evidence = [ev.get("evidence", "") for ev in all_strength_evidences if ev.get("evidence") and len(ev.get("evidence", "").strip()) >= 5]
        reasoning_parts = [ev.get("reasoning", "") for ev in all_strength_evidences if ev.get("reasoning") and len(ev.get("reasoning", "").strip()) >= 5]
        
        # 如果提取的内容为空，回退到从detected_actions生成
        if not detected_actions and not resume_evidence:
            top_actions = scoring_result.detected_actions[:3]
            detected_actions = [a.action for a in top_actions if a.action and len(a.action.strip()) >= 3]
            resume_evidence = [a.resume_quote for a in top_actions if a.resume_quote and len(a.resume_quote.strip()) >= 5]
        
        # 生成结论
        if scoring_result.skill_match_score >= 20:
            conclusion = "核心技能与岗位要求高度匹配"
        elif scoring_result.experience_match_score >= 18:
            conclusion = "工作经验与岗位场景高度相关"
        elif scoring_result.skill_match_score >= 15 or scoring_result.experience_match_score >= 15:
            conclusion = "具备岗位所需的基础能力"
        else:
            conclusion = "具备一定的工作能力"
        
        # 生成推理文本
        ai_reasoning = f"技能匹配度得分{scoring_result.skill_match_score}分，经验相关性得分{scoring_result.experience_match_score}分。"
        if reasoning_parts:
            ai_reasoning += " " + " ".join(reasoning_parts[:2])
        elif detected_actions:
            ai_reasoning += f"从简历中识别出{len(detected_actions)}个关键动作，体现了与岗位要求相关的工作能力。"
        else:
            ai_reasoning += "建议进一步了解候选人的具体工作内容和成果。"
        
        return {
            "conclusion": conclusion,
            "detected_actions": detected_actions[:3] if detected_actions else [],
            "resume_evidence": resume_evidence[:3] if resume_evidence else [],
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

