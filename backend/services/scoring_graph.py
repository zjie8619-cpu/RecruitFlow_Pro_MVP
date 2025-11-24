"""
AI 评分引擎 - 标准化推理框架
从简历文本到最终评分的完整推理链路（S1-S9）
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field

from backend.services.robust_parser import RobustParser, ParsingResult
from backend.services.ability_pool import AbilityPool, ActionMapping


@dataclass
class DetectedAction:
    """检测到的动作（Ultra版）"""
    action: str  # 完整动词短语，最少6字
    sentence: str  # 完整句子
    resume_quote: str  # 原文引用
    ability_tags: List[str] = field(default_factory=list)  # 能力标签（2-3个）
    confidence: float = 1.0


@dataclass
class EvidenceItem:
    """证据项"""
    dimension: str
    action: str
    resume_quote: str
    reasoning: str
    score_contribution: float = 0.0


@dataclass
class RiskItem:
    """风险项"""
    risk_type: str
    evidence: str
    reason: str
    severity: str = "medium"  # low, medium, high


@dataclass
class ScoringResult:
    """评分结果"""
    # 原始数据
    detected_actions: List[DetectedAction] = field(default_factory=list)
    evidence_chain: List[EvidenceItem] = field(default_factory=list)
    risks: List[RiskItem] = field(default_factory=list)
    
    # 维度分数（0-25）
    skill_match_score: float = 0.0
    experience_match_score: float = 0.0
    stability_score: float = 0.0
    growth_potential_score: float = 0.0
    
    # 总分（0-100）
    final_score: float = 0.0
    
    # 匹配度判断
    match_level: str = "无法评估"  # 强烈推荐/推荐/一般匹配/弱匹配/不推荐
    
    # 可解释性
    score_explanation: Dict[str, str] = field(default_factory=dict)
    
    # 错误信息
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class ScoringGraph:
    """标准化评分推理框架"""
    
    def __init__(self, job_title: str, jd_text: str = ""):
        self.job_title = job_title
        self.jd_text = jd_text
        self.parser = RobustParser()
        self.ability_pool = AbilityPool()
        self.action_mapping = ActionMapping()
        
    def execute(self, resume_text: str) -> ScoringResult:
        """
        执行完整的评分推理流程（S1-S9）
        """
        result = ScoringResult()
        
        try:
            # S1: 简历文本清洗
            cleaned_text, parse_result = self._step1_clean_text(resume_text)
            # 即使有错误码，也继续处理（只是标记为警告）
            # 只有严重错误（如完全空内容）才提前返回
            if parse_result.error_code == "EMPTY_CONTENT":
                result.error_code = parse_result.error_code
                result.error_message = parse_result.error_message
                return result
            # 其他错误（如文本过短、图片内容等）只标记为警告，继续处理
            if parse_result.error_code:
                result.error_code = parse_result.error_code
                result.error_message = parse_result.error_message
                # 不返回，继续执行后续步骤
            
            # S2: 动作识别
            import sys
            print(f"[DEBUG] S2: 开始动作识别，cleaned_text长度={len(cleaned_text)}", flush=True)
            sys.stdout.flush()
            detected_actions = self._step2_detect_actions(cleaned_text)
            result.detected_actions = detected_actions
            print(f"[DEBUG] S2: 动作识别完成，detected_actions数量={len(detected_actions)}", flush=True)
            sys.stdout.flush()
            
            # 如果动作过少，仍然继续处理，但标记为警告
            if len(detected_actions) < 2:
                # 不直接返回错误，而是继续处理，但会在最终结果中标记
                result.error_code = "INSUFFICIENT_ACTIONS"
                result.error_message = "简历中检测到的动作过少，评分可能不够准确"
                # 即使没有动作，也继续执行后续步骤，生成基本字段
                # 不再提前返回，让后续步骤生成默认的evidence_chain等字段
            
            # S3: 能力维度归类
            import sys
            print(f"[DEBUG] S3: 开始能力维度归类，detected_actions数量={len(detected_actions)}", flush=True)
            sys.stdout.flush()
            ability_mapping = self._step3_map_abilities(detected_actions)
            print(f"[DEBUG] S3: 能力维度归类完成，ability_mapping数量={len(ability_mapping)}", flush=True)
            sys.stdout.flush()
            
            # S4: 权重模型（岗位可切换）
            print(f"[DEBUG] S4: 开始权重模型计算", flush=True)
            sys.stdout.flush()
            weight_matrix = self._step4_weight_matrix()
            print(f"[DEBUG] S4: 权重模型计算完成", flush=True)
            sys.stdout.flush()
            
            # S5: 分数计算
            print(f"[DEBUG] S5: 开始分数计算", flush=True)
            sys.stdout.flush()
            dimension_scores = self._step5_calculate_scores(
                detected_actions, ability_mapping, weight_matrix
            )
            print(f"[DEBUG] S5: 分数计算完成: {dimension_scores}", flush=True)
            sys.stdout.flush()
            result.skill_match_score = dimension_scores["skill_match"]
            result.experience_match_score = dimension_scores["experience_match"]
            result.stability_score = dimension_scores["stability"]
            result.growth_potential_score = dimension_scores["growth_potential"]
            result.final_score = sum(dimension_scores.values())
            
            # S6: 风险识别
            import sys
            print(f"[DEBUG] S6: 开始风险识别", flush=True)
            sys.stdout.flush()
            risks = self._step6_identify_risks(cleaned_text, detected_actions, dimension_scores)
            result.risks = risks
            print(f"[DEBUG] S6: 风险识别完成，risks数量={len(risks)}", flush=True)
            sys.stdout.flush()
            
            # S7: 职业契合度判断
            print(f"[DEBUG] S7: 开始职业契合度判断", flush=True)
            sys.stdout.flush()
            match_level = self._step7_match_level(result.final_score, risks)
            result.match_level = match_level
            print(f"[DEBUG] S7: 职业契合度判断完成: {match_level}", flush=True)
            sys.stdout.flush()
            
            # S8: 生成解释
            print(f"[DEBUG] S8: 开始生成解释", flush=True)
            sys.stdout.flush()
            explanations = self._step8_generate_explanations(
                dimension_scores, detected_actions, ability_mapping, risks
            )
            result.score_explanation = explanations
            print(f"[DEBUG] S8: 生成解释完成", flush=True)
            sys.stdout.flush()
            
            # S9: 构建证据链
            print(f"[DEBUG] S9: 开始构建证据链", flush=True)
            sys.stdout.flush()
            evidence_chain = self._step9_build_evidence_chain(
                detected_actions, ability_mapping, dimension_scores
            )
            result.evidence_chain = evidence_chain
            print(f"[DEBUG] S9: 构建证据链完成，evidence_chain数量={len(evidence_chain)}", flush=True)
            sys.stdout.flush()
            
        except Exception as e:
            import traceback
            print(f"[ERROR] ScoringGraph.execute() 发生异常: {str(e)}")
            print(f"[ERROR] 异常堆栈: {traceback.format_exc()}")
            result.error_code = "SCORING_ERROR"
            result.error_message = f"评分过程发生错误: {str(e)}"
            # 即使有异常，也尝试生成基本的evidence_chain
            if len(result.evidence_chain) == 0:
                print(f"[DEBUG] 异常后生成默认evidence_chain")
                result.evidence_chain = [
                    EvidenceItem(
                        dimension="技能匹配度",
                        action="评分过程发生错误",
                        resume_quote="无法提取简历信息",
                        reasoning=f"错误: {str(e)}",
                        score_contribution=0.0
                    )
                ]
        
        import sys
        print(f"[DEBUG] ScoringGraph.execute() 最终返回: evidence_chain数量={len(result.evidence_chain)}, final_score={result.final_score}", flush=True)
        sys.stdout.flush()
        return result
    
    def _step1_clean_text(self, resume_text: str) -> Tuple[str, ParsingResult]:
        """S1: 简历文本清洗"""
        parse_result = self.parser.parse(resume_text)
        if parse_result.error_code:
            return resume_text, parse_result
        
        # 清洗文本
        cleaned = re.sub(r'\s+', ' ', parse_result.cleaned_text)
        cleaned = cleaned.strip()
        
        return cleaned, parse_result
    
    def _step2_detect_actions(self, text: str) -> List[DetectedAction]:
        """
        Ultra S2: 动作识别（强规则过滤）
        - 动作必须为"完整动词短语"
        - 最少6字以上才视为动作
        - 不得出现单字动作
        - 不得使用纯名词
        - 需匹配动词词典
        """
        # 标准动词词典
        VERB_DICT = ["管理", "分析", "优化", "提高", "制定", "协调", "带领", "复盘", 
                     "执行", "培训", "沟通", "计划", "跟进", "推动", "组织", "负责",
                     "完成", "开展", "实施", "维护", "服务", "回访", "督导", "辅导",
                     "指导", "策划", "设计", "开发", "总结", "改进", "提升", "达成",
                     "实现", "解决", "处理", "建立", "编写", "制作", "参与", "协助",
                     "支持", "配合", "提升", "改善", "优化", "完善", "加强", "深化"]
        
        actions = []
        sentences = re.split(r'[。！？；\n]', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            # 至少8字以上（与S1保持一致）
            if len(sentence) < 8:
                continue
            
            # 查找包含动词的完整短语（最少6字）
            for verb in VERB_DICT:
                if verb in sentence:
                    # 提取动词及其后的内容，形成完整短语
                    verb_pos = sentence.find(verb)
                    if verb_pos >= 0:
                        # 提取动词短语：动词 + 后续内容（至少到逗号、句号或6字）
                        phrase_start = max(0, verb_pos - 2)  # 可能包含"负责"等前置词
                        phrase_end = min(len(sentence), verb_pos + len(verb) + 20)  # 动词后20字
                        phrase = sentence[phrase_start:phrase_end]
                        
                        # 清理短语：去除前后标点和空格
                        phrase = re.sub(r'^[，。！？；：、\s]+', '', phrase)
                        phrase = re.sub(r'[，。！？；：、\s]+$', '', phrase)
                        
                        # 强规则过滤
                        if self._is_valid_action_phrase(phrase, verb):
                            # 映射能力标签
                            ability_tags = self.action_mapping.map_action_to_abilities(verb, sentence)
                            # 确保2-3个能力标签
                            if len(ability_tags) < 2:
                                # 补充能力标签
                                ability_tags.extend(self.ability_pool.match_abilities(sentence)[:3-len(ability_tags)])
                            ability_tags = ability_tags[:3]  # 最多3个
                            
                            actions.append(DetectedAction(
                                action=phrase[:50],  # 限制长度
                                sentence=sentence,
                                resume_quote=sentence[:100],
                                ability_tags=ability_tags,
                                confidence=1.0
                            ))
                            break  # 每个句子只提取一个主要动作
        
        # 去重：同一动作只保留1条
        unique_actions = []
        seen_actions = set()
        for action in actions:
            action_key = (action.action, action.sentence[:50])  # 使用动作和句子前50字作为key
            if action_key not in seen_actions:
                unique_actions.append(action)
                seen_actions.add(action_key)
        
        return unique_actions[:20]  # 最多20个动作
    
    def _is_valid_action_phrase(self, phrase: str, verb: str) -> bool:
        """
        验证动作短语是否有效
        - 最少6字以上
        - 不得是单字
        - 不得是纯名词
        - 必须包含动词
        """
        # 最少6字
        if len(phrase) < 6:
            return False
        
        # 不得是单字
        if len(phrase) == 1:
            return False
        
        # 必须包含动词
        if verb not in phrase:
            return False
        
        # 过滤纯名词（不包含动词的短语）
        # 检查是否包含动作性词汇
        action_indicators = ["管理", "分析", "优化", "提高", "制定", "协调", "带领", "复盘",
                           "执行", "培训", "沟通", "计划", "跟进", "推动", "组织", "负责"]
        has_action = any(indicator in phrase for indicator in action_indicators)
        if not has_action:
            return False
        
        # 过滤噪声：不得是纯标点或数字
        if re.match(r'^[，。！？；：、\s\d]+$', phrase):
            return False
        
        return True
    
    def _step3_map_abilities(self, actions: List[DetectedAction]) -> Dict[str, List[DetectedAction]]:
        """S3: 能力维度归类"""
        mapping = {}
        
        for action in actions:
            # 使用能力池映射
            abilities = self.action_mapping.map_action_to_abilities(action.action, action.resume_quote)
            
            for ability in abilities:
                if ability not in mapping:
                    mapping[ability] = []
                mapping[ability].append(action)
        
        return mapping
    
    def _step4_weight_matrix(self) -> Dict[str, float]:
        """S4: 权重模型（岗位可切换）"""
        # 根据岗位类型调整权重
        job_lower = self.job_title.lower()
        
        if any(kw in job_lower for kw in ["班主任", "学管", "教务", "教育"]):
            # 教育类岗位：更重视沟通和服务
            return {
                "skill_match": 0.30,
                "experience_match": 0.30,
                "stability": 0.25,
                "growth_potential": 0.15,
            }
        elif any(kw in job_lower for kw in ["销售", "顾问", "bd"]):
            # 销售类岗位：更重视经验和稳定性
            return {
                "skill_match": 0.25,
                "experience_match": 0.35,
                "stability": 0.25,
                "growth_potential": 0.15,
            }
        else:
            # 默认权重（均衡）
            return {
                "skill_match": 0.25,
                "experience_match": 0.25,
                "stability": 0.25,
                "growth_potential": 0.25,
            }
    
    def _step5_calculate_scores(
        self,
        actions: List[DetectedAction],
        ability_mapping: Dict[str, List[DetectedAction]],
        weight_matrix: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Ultra S4: 打分规则升级
        - 技能匹配度 = 关键岗位能力的权重 * 出现次数
        - 经验相关性 = 与岗位JD关键场景匹配程度
        - 成长潜力 = 晋升/跨部门/项目经验
        - 稳定性 = 岗位跨度 + 在职时长 + 跳槽频率
        """
        scores = {}
        core_abilities = self.ability_pool.get_core_abilities(self.job_title)
        
        # 技能匹配度（0-25）：关键岗位能力的权重 * 出现次数
        skill_actions = []
        skill_ability_counts = {}
        for ability, mapped_actions in ability_mapping.items():
            if ability in core_abilities:
                skill_actions.extend(mapped_actions)
                skill_ability_counts[ability] = len(mapped_actions)
        
        # 计算技能匹配度：核心能力出现次数加权
        skill_score = 0.0
        for ability, count in skill_ability_counts.items():
            # 每个核心能力最多贡献5分
            skill_score += min(5.0, count * 1.5)
        skill_score = min(25.0, skill_score)
        # 如果没有动作，给一个默认分数
        if len(actions) == 0:
            skill_score = 10.0
        scores["skill_match"] = round(skill_score, 1)
        
        # 经验相关性（0-25）：与岗位JD关键场景匹配程度
        # 检查JD中的关键场景词
        jd_keywords = []
        if self.jd_text:
            jd_sentences = re.split(r'[。！？；\n]', self.jd_text)
            for sent in jd_sentences[:10]:  # 前10句
                jd_keywords.extend(re.findall(r'[\u4e00-\u9fa5]{2,}', sent))
        
        # 计算简历动作与JD的匹配度
        match_count = 0
        for action in actions:
            for keyword in jd_keywords[:20]:  # 前20个关键词
                if keyword in action.sentence:
                    match_count += 1
                    break
        
        exp_score = min(25.0, (match_count * 2.0) + (len(actions) * 0.8))
        # 如果没有动作，给一个默认分数
        if len(actions) == 0:
            exp_score = 10.0
        scores["experience_match"] = round(exp_score, 1)
        
        # 稳定性（0-25）：岗位跨度 + 在职时长 + 跳槽频率
        # 从简历文本中提取工作年限
        years_match = re.search(r'(\d+)[年岁]', self.jd_text + " " + str(actions[0].sentence if actions else ""))
        years = float(years_match.group(1)) if years_match else 3.0
        
        # 计算跳槽频率（简单估算：工作年限/公司数量）
        company_count = len(re.findall(r'(公司|企业|机构|单位)', str(actions[0].sentence if actions else "")))
        company_count = max(1, company_count)
        job_span = years / company_count if company_count > 0 else years
        
        # 稳定性评分：工作年限越长、跳槽越少，分数越高
        if job_span >= 3:
            stability_score = 20.0
        elif job_span >= 2:
            stability_score = 15.0
        elif job_span >= 1:
            stability_score = 10.0
        else:
            stability_score = 5.0
        
        scores["stability"] = round(stability_score, 1)
        
        # 成长潜力（0-25）：晋升/跨部门/项目经验
        growth_keywords = ["学习", "培训", "复盘", "总结", "改进", "优化", "提升", "晋升", "跨部门", "项目"]
        growth_indicators = ["晋升", "提升", "优化", "改进", "跨", "项目", "负责", "带领"]
        growth_count = sum(1 for action in actions if any(kw in action.sentence for kw in growth_keywords))
        growth_indicators_count = sum(1 for action in actions if any(ind in action.sentence for ind in growth_indicators))
        
        growth_score = min(25.0, (growth_count * 2.5) + (growth_indicators_count * 1.5) + (len(actions) > 8) * 3.0)
        # 如果没有动作，给一个默认分数
        if len(actions) == 0:
            growth_score = 10.0
        scores["growth_potential"] = round(growth_score, 1)
        
        return scores
    
    def _step6_identify_risks(
        self,
        text: str,
        actions: List[DetectedAction],
        scores: Dict[str, float]
    ) -> List[RiskItem]:
        """S6: 风险识别"""
        risks = []
        
        # 检查动作数量
        if len(actions) < 3:
            risks.append(RiskItem(
                risk_type="动作证据不足",
                evidence=f"仅检测到{len(actions)}个动作",
                reason="简历描述过于简单，无法充分评估能力",
                severity="high"
            ))
        
        # 检查分数分布
        if scores["skill_match"] < 10:
            risks.append(RiskItem(
                risk_type="技能匹配度低",
                evidence=f"技能匹配度仅{scores['skill_match']}分",
                reason="核心技能与岗位要求差距较大",
                severity="high"
            ))
        
        if scores["stability"] < 10:
            risks.append(RiskItem(
                risk_type="稳定性风险",
                evidence=f"稳定性评分仅{scores['stability']}分",
                reason="可能存在跳槽频繁或任期较短的情况",
                severity="medium"
            ))
        
        # 检查文本长度
        if len(text) < 500:
            risks.append(RiskItem(
                risk_type="简历信息不足",
                evidence=f"简历文本仅{len(text)}字",
                reason="信息量不足，可能影响评估准确性",
                severity="medium"
            ))
        
        return risks[:3]  # 最多3个风险
    
    def _step7_match_level(self, final_score: float, risks: List[RiskItem]) -> str:
        """S7: 职业契合度判断"""
        high_risk_count = sum(1 for r in risks if r.severity == "high")
        
        if final_score >= 85 and high_risk_count == 0:
            return "强烈推荐"
        elif final_score >= 75 and high_risk_count <= 1:
            return "推荐"
        elif final_score >= 65:
            return "一般匹配"
        elif final_score >= 50:
            return "弱匹配"
        else:
            return "不推荐"
    
    def _step8_generate_explanations(
        self,
        scores: Dict[str, float],
        actions: List[DetectedAction],
        ability_mapping: Dict[str, List[DetectedAction]],
        risks: List[RiskItem]
    ) -> Dict[str, str]:
        """S8: 生成解释"""
        explanations = {}
        
        # 技能匹配度解释
        skill_actions_count = sum(len(actions) for ability, actions in ability_mapping.items() 
                                 if ability in self.ability_pool.get_core_abilities(self.job_title))
        explanations["skill_match"] = (
            f"检测到{skill_actions_count}个与岗位核心技能相关的动作，"
            f"覆盖{len(ability_mapping)}个能力维度，技能匹配度{scores['skill_match']}分"
        )
        
        # 经验相关性解释
        explanations["experience_match"] = (
            f"从简历中识别出{len(actions)}个有效动作，"
            f"经验相关性评分{scores['experience_match']}分"
        )
        
        # 稳定性解释
        explanations["stability"] = (
            f"基于工作经历分析，稳定性评分{scores['stability']}分"
        )
        
        # 成长潜力解释
        growth_actions = [a for a in actions if any(kw in a.resume_quote for kw in ["学习", "培训", "复盘"])]
        explanations["growth_potential"] = (
            f"识别出{len(growth_actions)}个体现学习成长的动作，"
            f"成长潜力评分{scores['growth_potential']}分"
        )
        
        return explanations
    
    def _step9_build_evidence_chain(
        self,
        actions: List[DetectedAction],
        ability_mapping: Dict[str, List[DetectedAction]],
        scores: Dict[str, float]
    ) -> List[EvidenceItem]:
        """S9: 构建证据链"""
        evidence_chain = []
        
        # 按维度构建证据
        dimensions = {
            "技能匹配度": "skill_match",
            "经验相关性": "experience_match",
            "稳定性": "stability",
            "成长潜力": "growth_potential",
        }
        
        for dim_name, dim_key in dimensions.items():
            # 获取该维度相关的动作
            if dim_key == "skill_match":
                relevant_actions = []
                for ability, mapped_actions in ability_mapping.items():
                    if ability in self.ability_pool.get_core_abilities(self.job_title):
                        relevant_actions.extend(mapped_actions)
            elif dim_key == "experience_match":
                relevant_actions = actions[:5]  # 前5个动作
            elif dim_key == "growth_potential":
                relevant_actions = [a for a in actions if any(kw in a.resume_quote for kw in ["学习", "培训", "复盘"])]
            else:
                relevant_actions = actions[:3]
            
            # 为每个动作创建证据项
            for action in relevant_actions[:3]:  # 每个维度最多3个证据
                # 生成更有意义的推理文本
                reasoning = self._generate_evidence_reasoning(action, dim_name, dim_key, scores)
                
                evidence_chain.append(EvidenceItem(
                    dimension=dim_name,
                    action=action.action,
                    resume_quote=action.resume_quote,
                    reasoning=reasoning,
                    score_contribution=scores[dim_key] / max(len(relevant_actions), 1)
                ))
            
            # 如果没有动作，为每个维度生成一个默认证据项
            if len(relevant_actions) == 0 and len(actions) == 0:
                default_reasoning = self._generate_default_reasoning(dim_name, dim_key, scores)
                evidence_chain.append(EvidenceItem(
                    dimension=dim_name,
                    action="简历信息不足",
                    resume_quote="简历中未检测到相关动作，建议进一步了解候选人情况",
                    reasoning=default_reasoning,
                    score_contribution=scores[dim_key]
                ))
        
        return evidence_chain
    
    def _generate_default_reasoning(self, dim_name: str, dim_key: str, scores: Dict[str, float]) -> str:
        """生成默认推理文本（当没有动作时）"""
        if dim_key == "skill_match":
            return f"技能匹配度得分{scores[dim_key]}分，简历信息不足，建议面试时重点考察核心技能"
        elif dim_key == "experience_match":
            return f"经验相关性得分{scores[dim_key]}分，简历信息不足，建议面试时深入了解工作经验"
        elif dim_key == "growth_potential":
            return f"成长潜力得分{scores[dim_key]}分，简历信息不足，建议面试时了解学习成长情况"
        else:
            return f"稳定性得分{scores[dim_key]}分，简历信息不足，建议面试时确认工作稳定性"
    
    def _generate_evidence_reasoning(
        self,
        action: DetectedAction,
        dim_name: str,
        dim_key: str,
        scores: Dict[str, float]
    ) -> str:
        """生成证据推理文本"""
        # 根据维度生成不同的推理文本
        if dim_key == "skill_match":
            # 技能匹配度：强调能力与岗位的匹配
            ability_tags_text = "、".join(action.ability_tags[:2]) if action.ability_tags else "相关能力"
            return f"该动作体现了{ability_tags_text}，与岗位核心技能要求匹配"
        elif dim_key == "experience_match":
            # 经验相关性：强调工作经验
            return f"该动作体现了与岗位场景相关的工作经验，具备实际操作能力"
        elif dim_key == "growth_potential":
            # 成长潜力：强调学习成长
            return f"该动作体现了学习成长能力，具备持续提升的潜力"
        else:
            # 稳定性：强调工作稳定性
            return f"该动作体现了工作稳定性，具备长期胜任岗位的能力"

