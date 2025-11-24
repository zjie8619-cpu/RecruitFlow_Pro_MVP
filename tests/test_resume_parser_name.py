import unittest

from backend.services.resume_parser import infer_candidate_name


class ResumeParserNameTests(unittest.TestCase):
    def test_structured_basic_info_block(self):
        text = """
        基本信息
        姓名：郭瑞民
        性别：男
        手机：13800001234
        """
        name = infer_candidate_name(text, "【HRBP_北京】_学士岗位.pdf")
        self.assertEqual(name, "郭瑞民")

    def test_neighbor_line_with_contact(self):
        text = """
        牛紫燕
        手机：13900001234
        邮箱：niu@example.com
        """
        name = infer_candidate_name(text, "课程顾问_学士崗位.pdf")
        self.assertEqual(name, "牛紫燕")

    def test_contact_section_in_middle(self):
        text = """
        教育背景
        Contact Information
        Name: Jason Chen
        Phone: +8613500000000
        """
        name = infer_candidate_name(text, "CMO-候选人.pdf")
        self.assertEqual(name, "Jason Chen")

    def test_filename_not_used_when_text_has_name(self):
        text = """
        个人简介
        我是牛紫燕，拥有丰富的校区管理经验，擅长家校沟通。
        """
        name = infer_candidate_name(text, "课程顾问_完成项目成交_5年简历.pdf")
        self.assertEqual(name, "牛紫燕")

    def test_filename_with_clear_name_used_only_as_fallback(self):
        text = ""
        name = infer_candidate_name(text, "产品经理_张三_2024版.pdf")
        self.assertEqual(name, "张三")

    def test_filename_without_name_returns_empty(self):
        text = ""
        name = infer_candidate_name(text, "课程顾问岗位需求2024.pdf")
        self.assertEqual(name, "")

    def test_award_phrase_not_used_as_name(self):
        text = """
        主要荣誉：理竞赛一等奖
        联系电话：13000000000
        """
        name = infer_candidate_name(text, "【物理竞赛教练_北京】杨致远 5年.pdf")
        self.assertEqual(name, "杨致远")

    def test_completion_phrase_not_used_as_name(self):
        text = """
        完成项目成交
        联系方式：13800000000
        """
        name = infer_candidate_name(text, "【课程顾问】李娜 3年.pdf")
        self.assertEqual(name, "李娜")


if __name__ == "__main__":
    unittest.main()



