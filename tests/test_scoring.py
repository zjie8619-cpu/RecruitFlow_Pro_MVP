"""
Ultra评分引擎单元测试
"""

import unittest
from backend.services.scoring_graph import ScoringGraph, ScoringResult
from backend.services.ultra_scoring_engine import UltraScoringEngine
from backend.services.robust_parser import RobustParser
from backend.services.ability_pool import AbilityPool
from backend.services.ultra_format_validator import UltraFormatValidator


class TestScoringGraph(unittest.TestCase):
    """测试评分推理框架"""
    
    def setUp(self):
        self.job_title = "课程顾问"
        self.jd_text = "负责学员管理、家长沟通、学习督导"
        self.resume_text = """
        张三，5年教育行业经验。
        负责学员管理，定期电话回访家长，跟进学习进度。
        组织家长会，策划活动方案，提升续班率。
        总结复盘，优化服务流程，提升客户满意度。
        """
    
    def test_step1_clean_text(self):
        """测试文本清洗"""
        graph = ScoringGraph(self.job_title, self.jd_text)
        cleaned, parse_result = graph._step1_clean_text(self.resume_text)
        
        self.assertIsNotNone(cleaned)
        self.assertGreater(len(cleaned), 0)
        self.assertTrue(parse_result.is_valid or parse_result.error_code is not None)
    
    def test_step2_detect_actions(self):
        """测试动作识别"""
        graph = ScoringGraph(self.job_title, self.jd_text)
        cleaned, _ = graph._step1_clean_text(self.resume_text)
        actions = graph._step2_detect_actions(cleaned)
        
        self.assertGreater(len(actions), 0)
        self.assertIsNotNone(actions[0].action)
        self.assertIsNotNone(actions[0].resume_quote)
    
    def test_full_execution(self):
        """测试完整执行流程"""
        graph = ScoringGraph(self.job_title, self.jd_text)
        result = graph.execute(self.resume_text)
        
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.final_score, 0)
        self.assertLessEqual(result.final_score, 100)
        self.assertGreater(len(result.detected_actions), 0)


class TestRobustParser(unittest.TestCase):
    """测试异常处理"""
    
    def setUp(self):
        self.parser = RobustParser()
    
    def test_empty_text(self):
        """测试空文本"""
        result = self.parser.parse("")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.error_code, "EMPTY_CONTENT")
    
    def test_short_text(self):
        """测试过短文本"""
        result = self.parser.parse("简短")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.error_code, "TEXT_TOO_SHORT")
    
    def test_normal_text(self):
        """测试正常文本"""
        text = "这是一份正常的简历文本，包含足够的内容用于评估。" * 20
        result = self.parser.parse(text)
        self.assertTrue(result.is_valid)


class TestUltraScoringEngine(unittest.TestCase):
    """测试Ultra评分引擎"""
    
    def setUp(self):
        self.job_title = "课程顾问"
        self.jd_text = "负责学员管理、家长沟通"
        self.resume_text = """
        李四，3年教育行业经验。
        负责学员管理，定期电话回访家长，跟进学习进度。
        组织家长会，策划活动方案。
        """
    
    def test_score(self):
        """测试评分"""
        engine = UltraScoringEngine(self.job_title, self.jd_text)
        result = engine.score(self.resume_text)
        
        self.assertIn("总分", result)
        self.assertIn("维度得分", result)
        self.assertIn("ai_review", result)
        self.assertIn("highlight_tags", result)
        self.assertIn("ai_resume_summary", result)
        self.assertIn("evidence_text", result)
        
        # 检查分数范围
        self.assertGreaterEqual(result["总分"], 0)
        self.assertLessEqual(result["总分"], 100)
    
    def test_ultra_format_compliance(self):
        """测试Ultra-Format合规性"""
        engine = UltraScoringEngine(self.job_title, self.jd_text)
        result = engine.score(self.resume_text)
        
        # 验证Ultra-Format
        is_valid, errors = UltraFormatValidator.validate(result)
        self.assertTrue(is_valid, f"Ultra-Format验证失败: {errors}")
        
        # 检查必需字段
        self.assertIn("score_detail", result)
        self.assertIn("persona_tags", result)  # 或 highlight_tags
        self.assertIn("strengths_reasoning_chain", result)
        self.assertIn("weaknesses_reasoning_chain", result)
        self.assertIn("resume_mini", result)
        self.assertIn("match_summary", result)
        self.assertIn("risks", result)
        
        # 检查推理链结构
        strengths_chain = result.get("strengths_reasoning_chain", {})
        if isinstance(strengths_chain, dict):
            self.assertIn("conclusion", strengths_chain)
            self.assertIn("detected_actions", strengths_chain)
            self.assertIn("resume_evidence", strengths_chain)
            self.assertIn("ai_reasoning", strengths_chain)
        
        weaknesses_chain = result.get("weaknesses_reasoning_chain", {})
        if isinstance(weaknesses_chain, dict):
            self.assertIn("conclusion", weaknesses_chain)
            self.assertIn("resume_gap", weaknesses_chain)
            self.assertIn("compare_to_jd", weaknesses_chain)
            self.assertIn("ai_reasoning", weaknesses_chain)
    
    def test_reasoning_chains_not_empty(self):
        """测试推理链不为空"""
        engine = UltraScoringEngine(self.job_title, self.jd_text)
        result = engine.score(self.resume_text)
        
        # 检查推理链是否存在且有内容
        strengths_chain = result.get("strengths_reasoning_chain", {})
        weaknesses_chain = result.get("weaknesses_reasoning_chain", {})
        
        self.assertIsNotNone(strengths_chain)
        self.assertIsNotNone(weaknesses_chain)
        
        # 至少应该有一个字段有内容
        if isinstance(strengths_chain, dict):
            has_content = any([
                strengths_chain.get("conclusion"),
                strengths_chain.get("detected_actions"),
                strengths_chain.get("resume_evidence"),
                strengths_chain.get("ai_reasoning")
            ])
            self.assertTrue(has_content, "优势推理链应该至少有一个字段有内容")
        
        if isinstance(weaknesses_chain, dict):
            has_content = any([
                weaknesses_chain.get("conclusion"),
                weaknesses_chain.get("resume_gap"),
                weaknesses_chain.get("compare_to_jd"),
                weaknesses_chain.get("ai_reasoning")
            ])
            self.assertTrue(has_content, "劣势推理链应该至少有一个字段有内容")
    
    def test_persona_tags_not_empty(self):
        """测试亮点标签不为空"""
        engine = UltraScoringEngine(self.job_title, self.jd_text)
        result = engine.score(self.resume_text)
        
        # 检查persona_tags或highlight_tags
        persona_tags = result.get("persona_tags", [])
        highlight_tags = result.get("highlight_tags", [])
        
        tags = persona_tags if persona_tags else highlight_tags
        self.assertIsInstance(tags, list)
        self.assertGreater(len(tags), 0, "亮点标签应该至少有一个")


class TestAbilityPool(unittest.TestCase):
    """测试能力池"""
    
    def setUp(self):
        self.pool = AbilityPool()
    
    def test_get_core_abilities(self):
        """测试获取核心能力"""
        abilities = self.pool.get_core_abilities("班主任")
        self.assertGreater(len(abilities), 0)
        self.assertIn("家校沟通", abilities)
    
    def test_match_abilities(self):
        """测试能力匹配"""
        text = "负责学员管理，定期电话回访家长，跟进学习进度"
        abilities = self.pool.match_abilities(text)
        self.assertGreater(len(abilities), 0)


class TestUltraFormatValidator(unittest.TestCase):
    """测试Ultra-Format验证器"""
    
    def test_validate_complete_result(self):
        """测试完整结果的验证"""
        result = {
            "score_detail": {
                "skill_match": {"score": 20, "evidence": []},
                "experience_match": {"score": 18, "evidence": []},
                "growth_potential": {"score": 15, "evidence": []},
                "stability": {"score": 12, "evidence": []},
                "final_score": 65
            },
            "persona_tags": ["执行力", "服务意识"],
            "strengths_reasoning_chain": {
                "conclusion": "具备核心能力",
                "detected_actions": ["负责", "组织"],
                "resume_evidence": ["负责学员管理"],
                "ai_reasoning": "技能匹配度高"
            },
            "weaknesses_reasoning_chain": {
                "conclusion": "存在不足",
                "resume_gap": ["缺少经验"],
                "compare_to_jd": "与JD要求有差距",
                "ai_reasoning": "经验不足"
            },
            "resume_mini": "3年教育行业经验",
            "match_summary": "推荐",
            "risks": []
        }
        
        is_valid, errors = UltraFormatValidator.validate(result)
        self.assertTrue(is_valid, f"验证失败: {errors}")
    
    def test_fix_missing_fields(self):
        """测试自动修复缺失字段"""
        result = {
            "score_detail": {"final_score": 65},
            "highlight_tags": ["执行力"],
            # 缺少其他字段
        }
        
        fixed = UltraFormatValidator.fix(result)
        
        # 检查是否添加了缺失字段
        self.assertIn("persona_tags", fixed)
        self.assertIn("resume_mini", fixed)
        self.assertIn("match_summary", fixed)
        self.assertIn("strengths_reasoning_chain", fixed)
        self.assertIn("weaknesses_reasoning_chain", fixed)
        self.assertIn("risks", fixed)


if __name__ == '__main__':
    unittest.main()

