"""
四个字段的 Ultra 版生成逻辑
"""

import re
import json
import textwrap
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
            except Exception as e:
                print(f"[WARNING] 无法获取LLM客户端: {str(e)}，将使用规则生成")
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
        # 尝试使用LLM生成
        try:
            client, cfg = self._get_llm_client()
            if client and cfg:
                return self._generate_ai_review_with_llm(
                    client, cfg, scoring_result, detected_actions, evidence_chain, risks
                )
        except Exception as e:
            print(f"[WARNING] LLM生成ai_review失败: {str(e)}，回退到规则生成", flush=True)
        
        # 回退到规则生成
        # ① 证据段
        evidence_section = self._build_evidence_section(detected_actions, evidence_chain, risks)
        
        # ② 推理段
        reasoning_section = self._build_reasoning_section(scoring_result, evidence_chain)
        
        # ③ 结论段
        conclusion_section = self._build_conclusion_section(scoring_result.final_score)
        
        # 组合
        review = f"{evidence_section}\n\n{reasoning_section}\n\n{conclusion_section}"
        
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
        （列出3-5条最重要的证据，每条为完整句子，引用简历原文）

        【推理】
        （分析各维度得分原因，使用25分制，说明为什么得分高或低）

        【结论】
        （基于总分给出推荐结论：强烈推荐/推荐/谨慎推荐/淘汰）

        ----------------------------------------------
        【注意事项】
        ----------------------------------------------
        1. 所有证据必须来自上述"检测到的动作"和"证据链"
        2. 推理部分必须明确说明各维度得分（使用25分制）
        3. 结论必须基于总分给出明确的推荐建议
        4. 不要输出JSON格式，直接输出文本
        5. 确保格式清晰，每段之间有换行
        """)
        
        try:
            response = chat_completion(
                client,
                cfg,
                messages=[
                    {"role": "system", "content": "你是一名专业的AI招聘评估官，能够生成结构化的候选人评价。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=800,
            )
            content = response["choices"][0]["message"]["content"]
            # 验证输出格式
            if "【证据】" in content and "【推理】" in content and "【结论】" in content:
                return content.strip()
            else:
                # 如果格式不对，回退到规则生成
                raise ValueError("LLM输出格式不正确")
        except Exception as e:
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
        
        # 格式化输出（确保每条都有换行，清理重复内容）
        if unique_sentences:
            for i, sent in enumerate(unique_sentences[:5], 1):
                # 清理句子：移除多余空格，确保格式统一
                clean_sent = re.sub(r'\s+', ' ', sent.strip())
                # 确保句子以句号结尾（如果没有标点）
                if clean_sent and not re.search(r'[。！？]$', clean_sent):
                    clean_sent += "。"
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
        
        # 逻辑树：分析各维度得分原因（分段显示，避免过长）
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # 分析最高分维度（独立段落）
        highest_dim, highest_score = sorted_scores[0]
        if highest_score >= 20:
            reasoning += f"{highest_dim}得分较高（{highest_score}分）。"
            if highest_dim == "技能匹配度":
                reasoning += "核心技能与岗位要求高度匹配。"
            elif highest_dim == "经验相关性":
                reasoning += "工作经验与岗位场景高度相关。"
            elif highest_dim == "成长潜力":
                reasoning += "学习成长能力突出。"
            else:
                reasoning += "工作稳定性良好。"
            reasoning += "\n"
        
        # 分析最低分维度（独立段落）
        lowest_dim, lowest_score = sorted_scores[-1]
        if lowest_score < 15:
            reasoning += f"{lowest_dim}得分较低（{lowest_score}分）。"
            if lowest_dim == "技能匹配度":
                reasoning += "核心技能与岗位要求存在差距。"
            elif lowest_dim == "经验相关性":
                reasoning += "工作经验与岗位场景匹配度不足。"
            elif lowest_dim == "成长潜力":
                reasoning += "学习成长能力有待提升。"
            else:
                reasoning += "工作稳定性存在风险。"
            reasoning += "\n"
        
        # 成长潜力 vs 经验匹配的平衡（独立段落）
        growth_exp_diff = scoring_result.growth_potential_score - scoring_result.experience_match_score
        if abs(growth_exp_diff) > 5:
            if growth_exp_diff > 0:
                reasoning += "成长潜力高于经验匹配，更适合培养型岗位。"
            else:
                reasoning += "经验匹配高于成长潜力，更适合即战力岗位。"
        else:
            reasoning += "成长潜力与经验匹配较为均衡。"
        reasoning += "\n"
        
        # 综合判断（独立段落）
        if scoring_result.final_score >= 75:
            reasoning += "综合能力较强，具备岗位所需的核心素质。"
        elif scoring_result.final_score >= 60:
            reasoning += "综合能力一般，存在一定优势但需关注薄弱环节。"
        else:
            reasoning += "综合能力较弱，与岗位要求存在较大差距。"
        
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
        - 从简历中实际提取能力（不过度依赖岗位JD）
        - 从能力池中选5-8个
        - 按出现频次排序
        - 不得出现无意义标签
        """
        # 收集所有能力标签及其出现次数（从简历中实际提取）
        ability_counts = {}
        
        # 从动作中收集能力标签（所有能力都收集，不过滤）
        for action in detected_actions:
            for ability in action.ability_tags:
                if ability in self.ability_pool.ABILITIES:  # 只保留标准能力池中的能力
                    ability_counts[ability] = ability_counts.get(ability, 0) + 1
        
        # 从证据链中收集能力标签
        for evidence in evidence_chain:
            # 从推理中提取能力关键词
            for ability in self.ability_pool.ABILITIES:
                if ability in evidence.reasoning:
                    ability_counts[ability] = ability_counts.get(ability, 0) + 1
        
        # 从动作的句子中直接匹配能力关键词
        for action in detected_actions:
            matched_abilities = self.ability_pool.match_abilities(action.sentence)
            for ability in matched_abilities:
                if ability in self.ability_pool.ABILITIES:
                    ability_counts[ability] = ability_counts.get(ability, 0) + 1
        
        # 按出现频次排序
        sorted_abilities = sorted(ability_counts.items(), key=lambda x: x[1], reverse=True)
        
        # 取前5-8个
        tags = [ability for ability, count in sorted_abilities[:8]]
        
        # 如果少于5个，从岗位核心能力中补充（但优先使用实际提取的能力）
        if len(tags) < 5:
            core_abilities = self.ability_pool.get_core_abilities(self.job_title)
            for ability in core_abilities:
                if ability not in tags:
                    tags.append(ability)
                    if len(tags) >= 5:
                        break
        
        # 如果还是少于5个，从通用能力中补充
        if len(tags) < 5:
            generic_abilities = ["执行力", "服务意识", "组织协调", "计划性", "抗压稳定"]
            for ability in generic_abilities:
                if ability not in tags:
                    tags.append(ability)
                    if len(tags) >= 5:
                        break
        
        # 确保至少5个，最多8个
        return tags[:8] if len(tags) >= 5 else (tags + ["执行力", "服务意识", "组织协调"])[:5]
    
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

