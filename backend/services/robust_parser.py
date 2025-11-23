"""
异常处理模块 - 处理各种异常情况
"""

from __future__ import annotations

from typing import Optional
from dataclasses import dataclass
import re


@dataclass
class ParsingResult:
    """解析结果"""
    cleaned_text: str = ""
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    is_valid: bool = True
    text_length: int = 0
    has_content: bool = False


class RobustParser:
    """健壮的文本解析器"""
    
    MIN_TEXT_LENGTH = 300  # 最小文本长度
    
    # 不相关岗位关键词（用于检测岗位不匹配）
    IRRELEVANT_JOBS = [
        "厨师", "护士", "医生", "机械", "司机", "保安", "保洁",
        "建筑", "装修", "电工", "焊工", "钳工", "木工"
    ]
    
    def parse(self, text: str) -> ParsingResult:
        """
        解析文本，检测异常情况
        """
        result = ParsingResult()
        
        if not text or not isinstance(text, str):
            result.error_code = "EMPTY_CONTENT"
            result.error_message = "简历内容为空或格式不正确"
            result.is_valid = False
            return result
        
        # 清洗文本
        cleaned = self._clean_text(text)
        result.cleaned_text = cleaned
        result.text_length = len(cleaned)
        result.has_content = len(cleaned.strip()) > 0
        
        # 检查文本长度
        if result.text_length < self.MIN_TEXT_LENGTH:
            result.error_code = "TEXT_TOO_SHORT"
            result.error_message = f"简历文本过短（{result.text_length}字），建议至少{self.MIN_TEXT_LENGTH}字"
            result.is_valid = False
            return result
        
        # 检查是否包含图片标记（OCR结果通常会有特殊标记）
        if self._is_image_content(cleaned):
            result.error_code = "IMAGE_CONTENT"
            result.error_message = "检测到图片内容，文本提取可能不完整"
            result.is_valid = False
            return result
        
        # 检查岗位相关性
        if self._is_irrelevant_job(cleaned):
            result.error_code = "JOB_MISMATCH"
            result.error_message = "简历岗位与目标岗位相关性较低"
            # 不设为无效，只是警告
        
        # 检查虚构内容
        fiction_issues = self._detect_fiction(cleaned)
        if fiction_issues:
            result.error_code = "POTENTIAL_FICTION"
            result.error_message = f"检测到可能的虚构内容: {fiction_issues}"
            # 不设为无效，只是警告
        
        return result
    
    def _clean_text(self, text: str) -> str:
        """
        Ultra S1: 文本清洗（增强版）
        - PDF断行修复
        - 去除噪声token
        - 去除电话/邮箱碎片
        - 至少8字以上才视为有效句
        """
        # 1. 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        
        # 2. PDF断行修复：合并异常断句（例如"退费率5：未开课阶段..."）
        # 修复模式：数字+冒号+短句 -> 合并
        text = re.sub(r'(\d+[：:])\s*([^\d]{1,10})\s*([。！？\n])', r'\1\2\3', text)
        # 修复模式：短句+冒号+短句 -> 合并
        text = re.sub(r'([^\d]{1,10}[：:])\s*([^\d]{1,10})\s*([。！？\n])', r'\1\2\3', text)
        
        # 3. 去除电话号码和邮箱导致的碎片
        # 移除电话号码模式
        text = re.sub(r'1[3-9]\d{9}', '', text)
        text = re.sub(r'\d{3,4}[- ]?\d{7,8}', '', text)
        # 移除邮箱模式
        text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', text)
        
        # 4. 移除特殊字符（保留中文、英文、数字、常用标点）
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？；：、\s]', '', text)
        
        # 5. 去除噪声token（单字词："务""开""组""分""理"等）
        noise_tokens = ["务", "开", "组", "分", "理", "管", "做", "有", "是", "的", "了", "在", "和", "与"]
        for token in noise_tokens:
            # 只移除独立的单字（前后有空格或标点）
            text = re.sub(rf'\s+{token}\s+', ' ', text)
            text = re.sub(rf'^{token}\s+', '', text)
            text = re.sub(rf'\s+{token}$', '', text)
        
        # 6. 按句子切分，至少8字以上才视为有效句
        sentences = re.split(r'[。！？；\n]', text)
        valid_sentences = []
        for s in sentences:
            s = s.strip()
            # 至少8字以上
            if len(s) >= 8:
                # 过滤掉纯数字、纯标点的句子
                if re.search(r'[\u4e00-\u9fa5a-zA-Z]', s):
                    valid_sentences.append(s)
        
        return '。'.join(valid_sentences)
    
    def _is_image_content(self, text: str) -> bool:
        """检测是否为图片内容"""
        # OCR结果通常包含这些标记
        image_indicators = [
            r'\[图片\]', r'\[图像\]', r'<img', r'image', r'photo',
            r'无法识别', r'识别失败', r'OCR'
        ]
        
        for pattern in image_indicators:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _is_irrelevant_job(self, text: str) -> bool:
        """检测岗位是否不相关"""
        text_lower = text.lower()
        
        for job in self.IRRELEVANT_JOBS:
            if job in text_lower:
                # 检查是否在岗位描述中（而不是在技能描述中）
                # 简单检查：如果出现在前200字，可能是岗位描述
                if job in text_lower[:200]:
                    return True
        
        return False
    
    def _detect_fiction(self, text: str) -> List[str]:
        """检测虚构内容（Ultra版）"""
        issues = []
        
        # 检查年份倒错
        years = re.findall(r'(19|20)\d{2}', text)
        if years:
            years_int = []
            for y in years:
                if len(y) == 4:
                    try:
                        years_int.append(int(y))
                    except:
                        pass
            if years_int:
                max_year = max(years_int)
                min_year = min(years_int)
                if max_year - min_year > 50:  # 工作年限超过50年
                    issues.append("工作年限异常（超过50年）")
        
        # 检查岗位与职责冲突
        # 例如：销售岗位但描述的是技术工作
        if "销售" in text and any(kw in text for kw in ["编程", "代码", "开发", "算法"]):
            if "销售" in text[:200] and any(kw in text[:500] for kw in ["编程", "代码"]):
                issues.append("岗位与职责描述可能存在冲突")
        
        return issues
    
    def format_error_message(self, error_code: str, error_message: str) -> str:
        """格式化错误信息为可读提示"""
        error_messages = {
            "EMPTY_CONTENT": "❌ 简历内容为空，请重新上传",
            "TEXT_TOO_SHORT": f"⚠️ 简历文本过短，可能影响评估准确性。建议补充更多信息。",
            "IMAGE_CONTENT": "⚠️ 检测到图片内容，文本提取可能不完整。建议使用文本格式的简历。",
            "JOB_MISMATCH": "⚠️ 简历岗位与目标岗位相关性较低，请确认是否匹配。",
            "POTENTIAL_FICTION": "⚠️ 检测到可能的异常内容，请核实简历真实性。",
        }
        
        return error_messages.get(error_code, f"⚠️ {error_message}")

