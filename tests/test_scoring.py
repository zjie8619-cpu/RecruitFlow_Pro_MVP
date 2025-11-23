"""
Ultra评分引擎单元测试
"""

import unittest
from backend.services.scoring_graph import ScoringGraph, ScoringResult
from backend.services.ultra_scoring_engine import UltraScoringEngine
from backend.services.robust_parser import RobustParser
from backend.services.ability_pool import AbilityPool


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


if __name__ == '__main__':
    unittest.main()

