"""
能力池映射模块
将动作映射到能力维度
"""

from typing import List, Dict, Set


class AbilityPool:
    """能力池定义（Ultra版 - 12大能力池）"""
    
    # 12类标准能力池
    ABILITIES = [
        "学生管理",
        "家校沟通",
        "学习指导",
        "数据复盘",
        "计划性",
        "执行力",
        "服务意识",
        "营销转化",
        "内容运营",
        "团队管理",
        "组织协调",
        "抗压稳定",
    ]
    
    # 能力关键词映射（Ultra版 - 更精确）
    ABILITY_KEYWORDS: Dict[str, List[str]] = {
        "学生管理": ["管理", "学员", "学生", "班级", "群体", "团队", "负责", "监督", "督促"],
        "家校沟通": ["家长", "家庭", "家校", "回访", "联系", "反馈", "沟通", "交流", "电话"],
        "学习指导": ["指导", "辅导", "教学", "授课", "讲解", "答疑", "督导", "督促", "学习"],
        "数据复盘": ["数据", "分析", "统计", "复盘", "总结", "报告", "评估", "优化", "改进"],
        "计划性": ["计划", "规划", "安排", "制定", "设计", "方案", "策划", "筹备"],
        "执行力": ["执行", "完成", "落实", "实施", "推进", "达成", "实现", "跟进"],
        "服务意识": ["服务", "维护", "支持", "协助", "帮助", "响应", "跟进", "关怀"],
        "营销转化": ["转化", "续班", "销售", "成交", "签约", "客户", "营销", "推广"],
        "内容运营": ["运营", "内容", "活动", "策划", "推广", "宣传", "传播"],
        "团队管理": ["团队", "带领", "管理", "协调", "配合", "协作", "组织"],
        "组织协调": ["组织", "协调", "配合", "协作", "沟通", "协调", "统筹"],
        "抗压稳定": ["压力", "挑战", "困难", "应对", "适应", "坚持", "稳定", "持续"],
    }
    
    # 岗位核心能力映射（Ultra版）
    JOB_CORE_ABILITIES: Dict[str, List[str]] = {
        "班主任": ["学生管理", "家校沟通", "学习指导", "执行力", "计划性"],
        "学管": ["学生管理", "家校沟通", "学习指导", "服务意识", "执行力"],
        "教务": ["执行力", "计划性", "服务意识", "数据复盘", "组织协调"],
        "课程顾问": ["家校沟通", "营销转化", "服务意识", "执行力", "抗压稳定"],
        "销售": ["营销转化", "执行力", "抗压稳定", "服务意识", "组织协调"],
    }
    
    def get_core_abilities(self, job_title: str) -> List[str]:
        """获取岗位核心能力（Ultra版）"""
        job_lower = job_title.lower()
        
        for job_key, abilities in self.JOB_CORE_ABILITIES.items():
            if job_key in job_lower:
                return abilities
        
        # 默认返回通用能力
        return ["执行力", "服务意识", "组织协调"]
    
    def match_abilities(self, text: str) -> List[str]:
        """匹配文本中的能力"""
        matched = []
        
        for ability, keywords in self.ABILITY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                matched.append(ability)
        
        return matched


class ActionMapping:
    """动作到能力的映射"""
    
    def __init__(self):
        self.ability_pool = AbilityPool()
    
    def map_action_to_abilities(self, action: str, context: str = "") -> List[str]:
        """将动作映射到能力"""
        # 结合动作和上下文进行匹配
        text = f"{action} {context}"
        abilities = self.ability_pool.match_abilities(text)
        
        # 如果没有匹配到，返回通用能力
        if not abilities:
            abilities = ["执行力"]
        
        return abilities
    
    def get_top_abilities(self, actions_with_context: List[tuple], limit: int = 5) -> List[str]:
        """获取最重要的能力（按出现频率）"""
        ability_counts = {}
        
        for action, context in actions_with_context:
            abilities = self.map_action_to_abilities(action, context)
            for ability in abilities:
                ability_counts[ability] = ability_counts.get(ability, 0) + 1
        
        # 按频率排序
        sorted_abilities = sorted(ability_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [ability for ability, _ in sorted_abilities[:limit]]

