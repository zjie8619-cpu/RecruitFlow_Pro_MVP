"""
四个字段的 Ultra 版生成逻辑
"""

import re
import json
import textwrap
import time
import sys
from typing import Dict, List, Any
from backend.services.scoring_graph import ScoringResult, DetectedAction, EvidenceItem, RiskItem
from backend.services.ability_pool import AbilityPool, ActionMapping
from backend.services.ai_client import get_client_and_cfg, chat_completion


class FieldGenerators:
    """字段生成器"""
    
    def __init__(self, job_title: str, jd_text: str = ""):
        self.job_title = job_title
        self.jd_text = jd_text
        self.ability_pool = AbilityPool()
        self.action_mapping = ActionMapping()
        self._llm_client = None
        self._llm_cfg = None
    
    def _get_llm_client(self):
        """获取LLM客户端（延迟初始化）"""
        if self._llm_client is None:
            try:
                self._llm_client, self._llm_cfg = get_client_and_cfg()
                # 检查API Key是否配置
                if not self._llm_cfg or not self._llm_cfg.api_key:
                    print(f"[WARNING] LLM API Key未配置，将使用规则生成", flush=True)
                    sys.stdout.flush()
                    return None, None
                print(f"[DEBUG] LLM客户端初始化成功: provider={self._llm_cfg.provider}, model={self._llm_cfg.model}", flush=True)
                sys.stdout.flush()
            except Exception as e:
                print(f"[WARNING] 无法获取LLM客户端: {str(e)}，将使用规则生成", flush=True)
                sys.stdout.flush()
                return None, None
        return self._llm_client, self._llm_cfg
    
    def generate_ai_review(
        self,
        scoring_result: ScoringResult,
        detected_actions: List[DetectedAction],
        evidence_chain: List[EvidenceItem],
        risks: List[RiskItem]
    ) -> str:
        """
        生成 AI 评价（Ultra Version）
        
        优先使用LLM生成，失败时回退到规则生成
        """
        start_time = time.time()
        print(f"[DEBUG] >>> 开始生成AI评价（LLM优先）", flush=True)
        sys.stdout.flush()
        
        # 尝试使用LLM生成
        try:
            client, cfg = self._get_llm_client()
            if client and cfg and cfg.api_key:
                print(f"[DEBUG] >>> 使用LLM生成AI评价...", flush=True)
                sys.stdout.flush()
                llm_start = time.time()
                result = self._generate_ai_review_with_llm(
                    client, cfg, scoring_result, detected_actions, evidence_chain, risks
                )
                llm_elapsed = time.time() - llm_start
                total_elapsed = time.time() - start_time
                print(f"[DEBUG] >>> LLM生成完成，耗时: {llm_elapsed:.2f}秒（总耗时: {total_elapsed:.2f}秒）", flush=True)
                sys.stdout.flush()
                return result
            else:
                print(f"[WARNING] >>> LLM客户端或API Key不可用，回退到规则生成", flush=True)
                sys.stdout.flush()
        except Exception as e:
            print(f"[WARNING] >>> LLM生成ai_review失败: {str(e)}，回退到规则生成", flush=True)
            sys.stdout.flush()
        
        # 回退到规则生成
        print(f"[DEBUG] >>> 使用规则生成AI评价...", flush=True)
        sys.stdout.flush()
        rule_start = time.time()
        
        # ① 证据段
        evidence_section = self._build_evidence_section(detected_actions, evidence_chain, risks)
        
        # ② 推理段
        reasoning_section = self._build_reasoning_section(scoring_result, evidence_chain)
        
        # ③ 结论段
        conclusion_section = self._build_conclusion_section(scoring_result.final_score)
        
        # 组合
        review = f"{evidence_section}\n\n{reasoning_section}\n\n{conclusion_section}"
        
        rule_elapsed = time.time() - rule_start
        total_elapsed = time.time() - start_time
        print(f"[DEBUG] >>> 规则生成完成，耗时: {rule_elapsed:.2f}秒（总耗时: {total_elapsed:.2f}秒）", flush=True)
        sys.stdout.flush()
        
        return review.strip()
    
    def _generate_ai_review_with_llm(
        self,
        client,
        cfg,
        scoring_result: ScoringResult,
        detected_actions: List[DetectedAction],
        evidence_chain: List[EvidenceItem],
        risks: List[RiskItem]
    ) -> str:
        """使用LLM生成AI评价"""
        print(f"[DEBUG] >>> 构建LLM提示词...", flush=True)
        sys.stdout.flush()
        
        # 构建证据摘要
        evidence_summary = []
        for ev in evidence_chain[:5]:
            if ev.resume_quote:
                evidence_summary.append(f"- {ev.action}: {ev.resume_quote[:100]}")
        
        # 构建动作摘要
        actions_summary = []
        for action in detected_actions[:5]:
            if action.sentence:
                actions_summary.append(f"- {action.sentence[:100]}")
        
        scores = {
            "技能匹配度": scoring_result.skill_match_score,
            "经验相关性": scoring_result.experience_match_score,
            "稳定性": scoring_result.stability_score,
            "成长潜力": scoring_result.growth_potential_score,
        }
        
        prompt = textwrap.dedent(f"""
        你是一名专业的AI招聘评估官。请基于以下信息生成结构化的AI评价。

        【岗位名称】
        {self.job_title}

        【岗位JD】
        {self.jd_text[:500] if self.jd_text else "未提供详细JD"}

        【候选人得分】
        {json.dumps(scores, ensure_ascii=False, indent=2)}
        总分: {scoring_result.final_score}

        【检测到的动作】
        {chr(10).join(actions_summary[:5]) if actions_summary else "无"}

        【证据链】
        {chr(10).join(evidence_summary[:5]) if evidence_summary else "无"}

        【风险项】
        {chr(10).join([f"- {r.risk_type}: {r.evidence[:100]}" for r in risks[:3]]) if risks else "无"}

        ----------------------------------------------
        【输出要求】
        ----------------------------------------------
        请严格按照以下三段式结构输出，不要添加额外内容：

        【证据】
        （列出3-5条最重要的证据，每条为完整句子，引用简历原文。确保句子通顺、完整，不要中途截断）

        【推理】
        （分析各维度得分原因，使用百分制（0-100分），说明为什么得分高或低。语言要自然流畅，逻辑清晰）

        【结论】
        （基于总分给出推荐结论：强烈推荐/推荐/谨慎推荐/淘汰。结论要简洁明确，语言通顺）

        ----------------------------------------------
        【注意事项】
        ----------------------------------------------
        1. 所有证据必须来自上述"检测到的动作"和"证据链"
        2. 推理部分必须明确说明各维度得分（使用百分制0-100分）
        3. 结论必须基于总分给出明确的推荐建议
        4. 不要输出JSON格式，直接输出文本
        5. 确保格式清晰，每段之间有换行
        6. 确保句子完整、通顺，不要中途截断
        7. 语言要自然流畅，避免生硬的模板化表达
        8. 每个句子都要完整，不要出现"1. 该候选人拥有15年的HRBP工作经验,主要负责技"这样的截断
        """)
        
        try:
            print(f"[DEBUG] >>> 调用LLM API (model={cfg.model})...", flush=True)
            sys.stdout.flush()
            api_start = time.time()
            
            response = chat_completion(
                client,
                cfg,
                messages=[
                    {"role": "system", "content": "你是一名专业的AI招聘评估官，能够生成结构化的候选人评价。请确保输出完整，不要中途截断句子。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=1200,  # 增加token限制，防止截断
                stop=["\n\n\n", "【证据】\n【证据】", "【推理】\n【推理】", "【结论】\n【结论】"],  # 防止重复和截断
            )
            
            api_elapsed = time.time() - api_start
            print(f"[DEBUG] >>> LLM API调用完成，耗时: {api_elapsed:.2f}秒", flush=True)
            sys.stdout.flush()
            
            content = response["choices"][0]["message"]["content"]
            print(f"[DEBUG] >>> LLM返回内容长度: {len(content)}字符", flush=True)
            sys.stdout.flush()
            
            # 验证输出格式
            if "【证据】" in content and "【推理】" in content and "【结论】" in content:
                print(f"[DEBUG] >>> LLM输出格式验证通过", flush=True)
                sys.stdout.flush()
                return content.strip()
            else:
                # 如果格式不对，回退到规则生成
                print(f"[WARNING] >>> LLM输出格式不正确，缺少必需段落", flush=True)
                sys.stdout.flush()
                raise ValueError("LLM输出格式不正确")
        except Exception as e:
            print(f"[ERROR] >>> LLM调用异常: {str(e)}", flush=True)
            sys.stdout.flush()
            raise Exception(f"LLM调用失败: {str(e)}")
    
    def _build_evidence_section(
        self,
        actions: List[DetectedAction],
        evidence_chain: List[EvidenceItem],
        risks: List[RiskItem]
    ) -> str:
        """
        Ultra S6: 构建证据段（严格结构化）
        - 列出3-5条最重要证据
        - 每条为完整句子
        - 不得出现拆开的断词
        """
        evidence_text = "【证据】"
        
        # 选择3-5条最重要的完整句子证据
        evidence_sentences = []
        
        # 从证据链中选择（优先选择技能匹配度和经验相关性的证据）
        priority_evidence = [e for e in evidence_chain if e.dimension in ["技能匹配度", "经验相关性"]]
        other_evidence = [e for e in evidence_chain if e.dimension not in ["技能匹配度", "经验相关性"]]
        
        # 优先证据取2-3条
        for ev in priority_evidence[:3]:
            if ev.resume_quote and len(ev.resume_quote.strip()) >= 8:
                evidence_sentences.append(ev.resume_quote.strip())
        
        # 其他证据取1-2条
        for ev in other_evidence[:2]:
            if ev.resume_quote and len(ev.resume_quote.strip()) >= 8 and ev.resume_quote not in evidence_sentences:
                evidence_sentences.append(ev.resume_quote.strip())
        
        # 如果证据不足，从动作中补充
        if len(evidence_sentences) < 3:
            for action in actions:
                if action.sentence and len(action.sentence.strip()) >= 8:
                    clean_sentence = action.sentence.strip()
                    if clean_sentence not in evidence_sentences:
                        evidence_sentences.append(clean_sentence)
                        if len(evidence_sentences) >= 5:
                            break
        
        # 去重并限制数量（3-5条）
        unique_sentences = []
        seen = set()
        for sent in evidence_sentences:
            # 清理句子：移除开头的数字和标点（如"2.6牵头组织" -> "牵头组织"）
            clean_sent = re.sub(r'^[\d\.\s]+', '', sent.strip())
            if clean_sent and len(clean_sent) >= 8:
                sent_key = clean_sent[:50]  # 使用前50字作为key
                if sent_key not in seen:
                    unique_sentences.append(clean_sent)
                    seen.add(sent_key)
                    if len(unique_sentences) >= 5:
                        break
        
        # 格式化输出（确保每条都有换行，清理重复内容，确保句子完整通顺）
        if unique_sentences:
            for i, sent in enumerate(unique_sentences[:5], 1):
                # 清理句子：移除多余空格，确保格式统一
                clean_sent = re.sub(r'\s+', ' ', sent.strip())
                # 确保句子完整：如果句子被截断（以逗号、顿号等结尾），尝试补全
                if clean_sent:
                    # 检查是否被截断（以逗号、顿号、冒号等结尾，且长度较短）
                    if re.search(r'[，、：；]$', clean_sent) and len(clean_sent) < 20:
                        # 可能是截断的句子，尝试从原文中找到完整句子
                        for action in actions:
                            if clean_sent[:10] in action.sentence:
                                clean_sent = action.sentence.strip()
                                break
                    # 确保句子以句号结尾（如果没有标点）
                    if clean_sent and not re.search(r'[。！？]$', clean_sent):
                        clean_sent += "。"
                    # 确保句子通顺：移除开头的数字和标点
                    clean_sent = re.sub(r'^[\d\.\s]+', '', clean_sent)
                    if clean_sent:
                        evidence_text += f"\n{i}. {clean_sent}"
        else:
            evidence_text += "\n暂无有效证据"
        
        return evidence_text
    
    def _build_reasoning_section(
        self,
        scoring_result: ScoringResult,
        evidence_chain: List[EvidenceItem]
    ) -> str:
        """
        Ultra S6: 构建推理段（逻辑树解释）
        - 用逻辑树解释为何得分高或低
        - 不得重复证据段
        """
        scores = {
            "技能匹配度": scoring_result.skill_match_score,
            "经验相关性": scoring_result.experience_match_score,
            "稳定性": scoring_result.stability_score,
            "成长潜力": scoring_result.growth_potential_score,
        }
        
        reasoning = "【推理】\n"
        
        # 逻辑树：分析各维度得分原因（分段显示，确保语言通顺自然）
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # 分析最高分维度（独立段落，语言自然流畅）
        highest_dim, highest_score = sorted_scores[0]
        if highest_score >= 80:
            if highest_dim == "技能匹配度":
                reasoning += f"技能匹配度得分{highest_score}分，表明候选人的核心技能与岗位要求高度匹配，能够胜任岗位所需的关键工作。"
            elif highest_dim == "经验相关性":
                reasoning += f"经验相关性得分{highest_score}分，表明候选人的工作经验与岗位场景高度相关，具备实际操作能力。"
            elif highest_dim == "成长潜力":
                reasoning += f"成长潜力得分{highest_score}分，表明候选人学习成长能力突出，具备持续提升的潜力。"
            else:
                reasoning += f"稳定性得分{highest_score}分，表明候选人工作稳定性良好，能够长期胜任岗位。"
            reasoning += "\n"
        
        # 分析最低分维度（独立段落，语言自然流畅）
        lowest_dim, lowest_score = sorted_scores[-1]
        if lowest_score < 60:
            if lowest_dim == "技能匹配度":
                reasoning += f"技能匹配度得分{lowest_score}分，相对较低，核心技能与岗位要求存在一定差距，建议面试时重点考察相关技能。"
            elif lowest_dim == "经验相关性":
                reasoning += f"经验相关性得分{lowest_score}分，相对较低，工作经验与岗位场景匹配度不足，建议进一步了解候选人的相关经验。"
            elif lowest_dim == "成长潜力":
                reasoning += f"成长潜力得分{lowest_score}分，相对较低，学习成长能力有待提升，建议评估候选人的学习意愿和能力。"
            else:
                reasoning += f"稳定性得分{lowest_score}分，相对较低，工作稳定性存在一定风险，建议面试时了解工作变动原因。"
            reasoning += "\n"
        
        # 成长潜力 vs 经验匹配的平衡（独立段落，语言自然流畅）
        growth_exp_diff = scoring_result.growth_potential_score - scoring_result.experience_match_score
        if abs(growth_exp_diff) > 15:
            if growth_exp_diff > 0:
                reasoning += "成长潜力明显高于经验匹配，候选人更适合培养型岗位，需要一定的培养周期。"
            else:
                reasoning += "经验匹配明显高于成长潜力，候选人更适合即战力岗位，能够快速上手工作。"
        elif abs(growth_exp_diff) > 5:
            if growth_exp_diff > 0:
                reasoning += "成长潜力略高于经验匹配，候选人具备一定的培养价值。"
            else:
                reasoning += "经验匹配略高于成长潜力，候选人更偏向即战力类型。"
        else:
            reasoning += "成长潜力与经验匹配较为均衡，候选人能力结构相对完整。"
        reasoning += "\n"
        
        # 综合判断（独立段落，语言自然流畅）
        if scoring_result.final_score >= 75:
            reasoning += f"综合得分{scoring_result.final_score}分，表明候选人综合能力较强，具备岗位所需的核心素质，建议优先考虑。"
        elif scoring_result.final_score >= 60:
            reasoning += f"综合得分{scoring_result.final_score}分，表明候选人综合能力一般，存在一定优势但需关注薄弱环节，建议结合岗位具体要求综合评估。"
        else:
            reasoning += f"综合得分{scoring_result.final_score}分，表明候选人综合能力较弱，与岗位要求存在较大差距，建议谨慎考虑。"
        
        return reasoning.strip()
    
    def _build_conclusion_section(self, final_score: float) -> str:
        """
        Ultra S6: 构建结论段（严格模板）
        - 必须是"强烈推荐/谨慎推荐/淘汰"之一
        """
        if final_score >= 85:
            conclusion = "【结论】强烈推荐。该候选人综合能力突出，可直接推进面试或offer流程。"
        elif final_score >= 75:
            conclusion = "【结论】推荐。该候选人表现较强，具备岗位所需的核心能力，建议安排面试。"
        elif final_score >= 65:
            conclusion = "【结论】谨慎推荐。该候选人有一定亮点，但存在关键风险点，需结合岗位具体要求综合评估。"
        elif final_score >= 50:
            conclusion = "【结论】谨慎推荐。该候选人与岗位要求存在一定差距，建议进一步评估。"
        else:
            conclusion = "【结论】淘汰。该候选人明显不符合岗位需求，不建议推进。"
        
        return conclusion
    
    def generate_highlight_tags(
        self,
        detected_actions: List[DetectedAction],
        evidence_chain: List[EvidenceItem]
    ) -> List[str]:
        """
        Ultra S7: 生成亮点标签（必须至少5个）
        - 标签必须真实来源于简历解析内容，不允许生成虚构能力标签
        - 完全禁止幻觉
        - 标签必须来源于证据链或原文动作
        - 严格验证：标签必须在简历原文中出现，不能从岗位JD推断
        """
        # 收集所有能力标签及其出现次数（从简历中实际提取，禁止虚构）
        ability_counts = {}
        
        # 收集所有简历原文文本（用于严格验证）
        all_resume_text = set()
        for action in detected_actions:
            all_resume_text.add(action.sentence.lower())
            all_resume_text.add(action.resume_quote.lower())
        for evidence in evidence_chain:
            all_resume_text.add(evidence.resume_quote.lower())
        
        # 从动作中收集能力标签（只收集实际检测到的，并严格验证）
        for action in detected_actions:
            for ability in action.ability_tags:
                if ability in self.ability_pool.ABILITIES:
                    # 严格验证：能力标签必须在简历原文中出现
                    ability_lower = ability.lower()
                    if any(ability_lower in text for text in all_resume_text):
                        ability_counts[ability] = ability_counts.get(ability, 0) + 1
        
        # 从证据链的动作中收集能力标签（只从action字段，严格验证）
        for evidence in evidence_chain:
            # 从证据的动作中匹配能力关键词（只从action字段，确保真实）
            matched_abilities = self.ability_pool.match_abilities(evidence.action)
            for ability in matched_abilities:
                if ability in self.ability_pool.ABILITIES:
                    # 严格验证：能力标签必须在简历原文中出现
                    ability_lower = ability.lower()
                    if any(ability_lower in text for text in all_resume_text):
                        ability_counts[ability] = ability_counts.get(ability, 0) + 1
        
        # 从动作的句子中直接匹配能力关键词（确保来自原文，并严格验证）
        for action in detected_actions:
            matched_abilities = self.ability_pool.match_abilities(action.sentence)
            for ability in matched_abilities:
                if ability in self.ability_pool.ABILITIES:
                    # 严格验证：能力标签必须在简历原文中出现
                    ability_lower = ability.lower()
                    if any(ability_lower in text for text in all_resume_text):
                        ability_counts[ability] = ability_counts.get(ability, 0) + 1
        
        # 按出现频次排序
        sorted_abilities = sorted(ability_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 取前5-8个（只取真实提取的标签）
        tags = [ability for ability, count in sorted_abilities[:8]]
        
        # 如果少于5个，从通用能力中补充（但必须严格验证有证据）
        if len(tags) < 5:
            # 根据简历内容动态选择通用能力，而不是固定列表
            generic_ability_candidates = []
            
            # 分析简历内容，提取可能的能力
            resume_text_combined = " ".join(all_resume_text)
            
            # 根据简历内容匹配通用能力
            generic_abilities_map = {
                "执行力": ["执行", "完成", "落实", "实施", "推进", "达成", "实现", "跟进", "负责"],
                "服务意识": ["服务", "维护", "支持", "协助", "帮助", "响应", "跟进", "关怀", "客户"],
                "组织协调": ["组织", "协调", "配合", "协作", "沟通", "统筹", "安排", "管理"],
                "计划性": ["计划", "规划", "安排", "制定", "设计", "方案", "策划", "筹备"],
                "抗压稳定": ["压力", "挑战", "困难", "应对", "适应", "坚持", "稳定", "持续"],
                "沟通表达": ["沟通", "表达", "交流", "沟通", "汇报", "反馈", "传达"],
                "团队协作": ["团队", "协作", "配合", "合作", "共同", "一起"],
                "数据分析": ["数据", "分析", "统计", "报表", "指标", "评估"],
            }
            
            for ability, keywords in generic_abilities_map.items():
                # 检查简历中是否有相关关键词
                if any(kw in resume_text_combined for kw in keywords):
                    if ability not in tags:
                        generic_ability_candidates.append(ability)
            
            # 按匹配度排序，取前几个
            for ability in generic_ability_candidates[:5]:
                if ability not in tags:
                    tags.append(ability)
                    if len(tags) >= 5:
                        break
        
        # 如果仍然少于5个，只返回实际提取的标签（禁止虚构）
        # 禁止从岗位JD推断标签，禁止添加未在简历中出现的标签
        return tags[:8] if len(tags) >= 5 else tags[:5] if len(tags) > 0 else []
    
    def generate_ai_resume_summary(
        self,
        resume_text: str,
        detected_actions: List[DetectedAction],
        evidence_chain: List[EvidenceItem]
    ) -> str:
        """
        Ultra S8: 生成AI短板简历（必须有价值）
        - 生成2-3条可面试追问点
        - 不能是"信息不足"等废话
        """
        weak_points = []
        
        # 分析动作数量
        if len(detected_actions) < 5:
            weak_points.append("简历描述较为简单，建议面试时深入了解具体工作内容和成果")
        
        # 分析能力覆盖度
        all_abilities = set()
        for action in detected_actions:
            all_abilities.update(action.ability_tags)
        core_abilities = set(self.ability_pool.get_core_abilities(self.job_title))
        missing_abilities = core_abilities - all_abilities
        
        if missing_abilities:
            weak_points.append(f"缺少{', '.join(list(missing_abilities)[:2])}等核心能力的明确体现，建议面试时重点考察")
        
        # 分析稳定性
        stability_keywords = ["年", "持续", "稳定", "长期"]
        has_stability_evidence = any(
            any(kw in action.sentence for kw in stability_keywords)
            for action in detected_actions
        )
        if not has_stability_evidence:
            weak_points.append("简历中缺少工作稳定性的明确信息，建议面试时确认工作年限和跳槽原因")
        
        # 如果不足2条，补充通用追问点
        if len(weak_points) < 2:
            weak_points.append("建议面试时深入了解候选人的具体工作成果和量化指标")
        
        # 限制2-3条
        return weak_points[:3]
    
    def generate_evidence_text(
        self,
        evidence_chain: List[EvidenceItem]
    ) -> str:
        """
        Ultra S5: 生成证据文本（去重 + 聚类 + 排版）
        - 同一动作仅保留1条
        - 每个维度最多输出3条
        - 删除重复句子
        - 删除标点碎片句子
        - 输出顺序：技能 → 经验 → 成长 → 稳定
        """
        if not evidence_chain:
            return "暂无有效证据"
        
        # 按维度分组（固定顺序）
        dimension_order = ["技能匹配度", "经验相关性", "成长潜力", "稳定性"]
        evidence_by_dimension = {dim: [] for dim in dimension_order}
        
        for evidence in evidence_chain:
            dim = evidence.dimension
            if dim in evidence_by_dimension:
                evidence_by_dimension[dim].append(evidence)
        
        # 去重：同一动作仅保留1条
        seen_actions = set()
        cleaned_evidence_by_dimension = {}
        
        for dim, evidences in evidence_by_dimension.items():
            cleaned = []
            for ev in evidences:
                action_key = (ev.action[:30], ev.resume_quote[:50])
                if action_key not in seen_actions:
                    # 过滤标点碎片句子
                    if len(ev.resume_quote.strip()) >= 8:
                        cleaned.append(ev)
                        seen_actions.add(action_key)
                        if len(cleaned) >= 3:  # 每个维度最多3条
                            break
            cleaned_evidence_by_dimension[dim] = cleaned
        
        # 构建文本（按固定顺序，确保格式清晰）
        evidence_text = ""
        for dim in dimension_order:
            evidences = cleaned_evidence_by_dimension.get(dim, [])
            if evidences:
                evidence_text += f"\n【{dim}】\n"
                for i, ev in enumerate(evidences, 1):
                    # 清理动作和证据：移除开头的数字和标点
                    clean_action = re.sub(r'^[\d\.\s]+', '', ev.action.strip())
                    clean_quote = re.sub(r'^[\d\.\s]+', '', ev.resume_quote.strip())
                    clean_reasoning = ev.reasoning.strip()
                    
                    # 限制长度，确保可读性
                    if len(clean_quote) > 100:
                        clean_quote = clean_quote[:100] + "..."
                    if len(clean_reasoning) > 80:
                        clean_reasoning = clean_reasoning[:80] + "..."
                    
                    evidence_text += (
                        f"{i}. 动作：{clean_action}\n"
                        f"   原文证据：{clean_quote}\n"
                        f"   推理：{clean_reasoning}\n"
                    )
                # 维度之间添加空行
                evidence_text += "\n"
        
        return evidence_text.strip() if evidence_text else "暂无有效证据"
    
    def generate_summary_short(
        self,
        resume_text: str,
        detected_actions: List[DetectedAction],
        highlight_tags: List[str],
        evidence_chain: List[EvidenceItem]
    ) -> str:
        """
        Ultra格式：生成三行结构化简历摘要
        ① 基础信息（年龄、学历、年限）
        ② 核心标签
        ③ 关键经历总结
        """
        lines = []
        
        # ① 基础信息（从简历开头提取）
        basic_info = ""
        resume_lines = resume_text.split('\n')[:10]
        for line in resume_lines:
            line = line.strip()
            # 提取年龄
            age_match = re.search(r'(\d{2})[岁]', line)
            age = age_match.group(1) if age_match else None
            # 提取学历
            education_keywords = ["本科", "硕士", "博士", "专科", "高中"]
            education = next((kw for kw in education_keywords if kw in line), None)
            # 提取年限
            years_match = re.search(r'(\d+)[年]', line)
            years = years_match.group(1) if years_match else None
            
            if age or education or years:
                parts = []
                if age:
                    parts.append(f"{age}岁")
                if education:
                    parts.append(education)
                if years:
                    parts.append(f"{years}年经验")
                if parts:
                    basic_info = "，".join(parts)
                    break
        
        if not basic_info:
            basic_info = "具备相关工作经验"
        lines.append(basic_info)
        
        # ② 核心标签（从highlight_tags中取前3个）
        if highlight_tags:
            core_tags = highlight_tags[:3]
            tags_text = "、".join(core_tags)
            lines.append(f"核心能力：{tags_text}")
        else:
            lines.append("核心能力：待评估")
        
        # ③ 关键经历总结（从detected_actions中取前2个）
        if detected_actions:
            key_actions = detected_actions[:2]
            actions_text = "、".join([a.action[:15] for a in key_actions])
            lines.append(f"关键经历：{actions_text}")
        else:
            lines.append("关键经历：待补充")
        
        return "\n".join(lines)
    
    def generate_resume_summary_original(
        self,
        resume_text: str,
        detected_actions: List[DetectedAction],
        evidence_chain: List[EvidenceItem]
    ) -> str:
        """
        生成原始简历摘要（用于显示）
        - 从简历文本中提取关键信息
        - 结合检测到的动作生成摘要
        """
        if not resume_text or len(resume_text.strip()) < 50:
            return "简历信息不足，无法生成详细摘要"
        
        # 提取基本信息
        lines = resume_text.split('\n')
        basic_info = ""
        
        # 从简历开头提取姓名、年龄、学历等信息
        for line in lines[:15]:
            line = line.strip()
            if not line:
                continue
            
            # 提取姓名（通常在开头）
            if len(line) <= 10 and not basic_info:
                # 可能是姓名
                name_match = re.search(r'^[\u4e00-\u9fa5]{2,4}', line)
                if name_match:
                    basic_info = name_match.group(0)
                    break
        
        # 提取工作经验和关键动作
        summary_parts = []
        
        # 如果有检测到的动作，使用动作生成摘要
        if detected_actions:
            # 取前3个最重要的动作
            key_actions = detected_actions[:3]
            action_texts = []
            for action in key_actions:
                # 清理动作文本
                clean_action = re.sub(r'^[\d\.\s]+', '', action.action.strip())
                if clean_action and len(clean_action) >= 6:
                    action_texts.append(clean_action[:30])
            
            if action_texts:
                summary_parts.append("、".join(action_texts))
        
        # 如果动作不足，从简历文本中提取关键句子
        if len(summary_parts) < 2:
            # 查找包含关键动词的句子
            key_verbs = ["负责", "管理", "组织", "实施", "完成", "达成", "提升", "优化"]
            for line in lines[:30]:
                line = line.strip()
                if any(verb in line for verb in key_verbs) and len(line) >= 15:
                    clean_line = re.sub(r'^[\d\.\s]+', '', line)
                    if clean_line and clean_line not in summary_parts:
                        summary_parts.append(clean_line[:50])
                        if len(summary_parts) >= 3:
                            break
        
        # 组合摘要
        if summary_parts:
            summary = "，".join(summary_parts[:3])
            if basic_info:
                return f"{basic_info}，{summary}"
            return summary
        else:
            # 如果无法提取，返回基本信息
            if basic_info:
                return f"{basic_info}，具备相关工作经验"
            return "具备相关工作经验"

