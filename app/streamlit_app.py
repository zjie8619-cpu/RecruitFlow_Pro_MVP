import json
import os
import re
import time
import uuid

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict
# 可选导入 plotly，如果不存在则使用替代方案
try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    go = None
from backend.storage.db import init_db, get_db
from backend.services.pipeline import RecruitPipeline
from backend.services.reporting import export_round_report
from backend.utils.versioning import VersionManager
from backend.utils.field_mapping import translate_dataframe_columns, translate_field
# 强制重新加载模块，避免缓存问题
import importlib
import sys
if 'backend.services.jd_ai' in sys.modules:
    importlib.reload(sys.modules['backend.services.jd_ai'])
from backend.services.jd_ai import generate_jd_bundle, construct_full_ability_list
from backend.services.resume_parser import parse_uploaded_files_to_df
# 🔄 确保 AI 匹配逻辑更新时立即生效
if 'backend.services.ai_matcher' in sys.modules:
    importlib.reload(sys.modules['backend.services.ai_matcher'])
from backend.services.ai_matcher import ai_match_resumes_df
from backend.services.ai_matcher_ultra import ai_match_resumes_df_ultra
from backend.services.ai_core import generate_ai_summary, generate_ai_email
# 🔄 强制重新加载日历工具模块，确保使用最新版本
if 'backend.services.calendar_utils' in sys.modules:
    importlib.reload(sys.modules['backend.services.calendar_utils'])
# 删除可能存在的旧导入
if 'create_ics_file' in globals():
    del create_ics_file
from backend.services.calendar_utils import create_ics_file

def add_name_title(name: str, row_dict: dict = None) -> str:
    """
    给姓名添加先生/女士称呼
    
    Args:
        name: 候选人姓名
        row_dict: 候选人数据字典（可选，用于提取性别信息）
    
    Returns:
        带称呼的姓名，如"张三先生"或"李四女士"
    """
    if not name or name == "匿名候选人":
        return "先生/女士"
    
    # 尝试从数据中提取性别信息
    gender = None
    if row_dict:
        # 尝试从多个可能的字段中提取性别
        gender_text = str(row_dict.get("gender", "") or row_dict.get("性别", "") or "").strip()
        if "女" in gender_text:
            gender = "女"
        elif "男" in gender_text:
            gender = "男"
    
    # 如果没有明确的性别信息，尝试从姓名判断（简单规则）
    if not gender:
        # 常见女性名字特征（简单判断，不准确但可用）
        female_name_chars = ["霞", "芳", "娜", "敏", "静", "丽", "艳", "红", "玲", "雪", "梅", "兰", "菊", "莲", "花", "月", "春", "秋", "冬", "美", "秀", "英", "华", "慧", "娟", "莉", "萍", "燕", "凤", "婷", "欣", "悦", "怡", "琳", "莹", "雯", "雅", "洁", "倩", "薇", "茜", "蓉", "菲", "瑶", "璐", "瑾", "璇", "璐", "璐", "璐"]
        # 如果名字最后一个字在女性名字特征中，使用"女士"
        if len(name) >= 2 and name[-1] in female_name_chars:
            gender = "女"
        else:
            # 默认使用"先生"
            gender = "男"
    
    return f"{name}{'女士' if gender == '女' else '先生'}"
# from backend.services.excel_exporter import generate_competency_excel, export_ability_sheet_to_file  # 函数不存在，已注释


def _ensure_job_meta() -> dict:
    """确保 session_state 中存在 job_meta 并返回引用。"""
    if "job_meta" not in st.session_state:
        st.session_state["job_meta"] = {}
    return st.session_state["job_meta"]


def _update_job_meta(*, job_name: str = None, must: str = None, nice: str = None, exclude: str = None) -> None:
    """将岗位名称与任职要求元数据写入 session_state."""
    meta = _ensure_job_meta()
    if job_name:
        meta["job_name"] = job_name
    if must:
        meta["job_must_have_skills"] = must
    if nice:
        meta["job_bonus_skills"] = nice
    if exclude:
        meta["job_exclude_list"] = exclude


def _build_invite_lookup(invites) -> Dict[str, Dict[str, Any]]:
    """将邀约结果转换为可在导出时查找的字典。"""
    lookup: Dict[str, Dict[str, Any]] = {}
    if not invites:
        return lookup
    for invite in invites:
        if not isinstance(invite, dict):
            continue
        meta = {
            "interview_time": invite.get("interview_time"),
            "interview_location": invite.get("interview_location"),
            "ics_path": invite.get("ics") or invite.get("ics_path", ""),
            "email_subject": invite.get("subject"),
            "email_sent": invite.get("email_sent"),
            "email_sent_at": invite.get("email_sent_at"),
            "email_status": invite.get("email_status"),
            "wechat_sent": invite.get("wechat_sent"),
            "email": invite.get("email"),
            "candidate_id": invite.get("candidate_id"),
            "file": invite.get("file") or invite.get("resume_file"),
        }
        keys = set()
        cand_id = str(invite.get("candidate_id") or "").strip()
        if cand_id:
            keys.add(cand_id)
        email = (invite.get("email") or "").strip().lower()
        if email:
            keys.add(email)
        file_token = str(invite.get("file") or invite.get("resume_file") or "").strip()
        if file_token:
            keys.add(file_token)
        for key in keys:
            lookup[key] = {k: v for k, v in meta.items() if v not in (None, "", [])}
    return lookup

# 强制重新加载 Excel 导出模块，确保模板样式调整后前端立即生效
if 'backend.services.export_excel' in sys.modules:
    importlib.reload(sys.modules['backend.services.export_excel'])
from backend.services.export_excel import export_competency_excel
from dotenv import load_dotenv

# 尝试从多个位置加载.env文件
env_paths = [
    Path('.env'),  # 当前目录（app/）
    Path('../.env'),  # 项目根目录
    Path(__file__).parent.parent / '.env',  # 项目根目录（绝对路径）
]
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break
else:
    load_dotenv()  # 默认加载

# --- session 初始化（放在 import 之后）---
if "ai_bundle" not in st.session_state:
    st.session_state["ai_bundle"] = None

# ============ 控制显示部分 ============
SHOW_OFFLINE_SECTION = False   # 是否显示“离线规则版”
SHOW_DETAIL_SECTIONS = True   # 是否显示详细部分（长版JD / 岗位能力维度 / 面试题等）
# =====================================

st.set_page_config(page_title="RecruitFlow | 一键招聘流水线", layout="wide")

# ==================== UI 优化样式 ====================
st.markdown("""
<style>
    /* 简历摘要3行限制 */
    .resume-mini {
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
        text-overflow: ellipsis;
        line-height: 1.5;
        max-height: 4.5em;
    }
    
    /* 亮点标签样式 */
    .highlight-tag {
        display: inline-block;
        padding: 4px 12px;
        margin: 4px 4px 4px 0;
        border-radius: 16px;
        font-size: 0.85em;
        font-weight: 500;
        white-space: nowrap;
    }
    
    .highlight-tag-green {
        background-color: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    
    .highlight-tag-yellow {
        background-color: #fff3cd;
        color: #856404;
        border: 1px solid #ffeaa7;
    }
    
    .highlight-tag-gray {
        background-color: #e9ecef;
        color: #495057;
        border: 1px solid #dee2e6;
    }
    
    /* 概览卡片样式 */
    .candidate-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .candidate-card h3 {
        color: white;
        margin: 0 0 10px 0;
        font-size: 1.5em;
    }
    
    .candidate-card .score {
        font-size: 2em;
        font-weight: bold;
        margin: 10px 0;
    }
    
    /* 推理链卡片样式 */
    .reasoning-item {
        background: #f8f9fa;
        padding: 15px;
        margin: 10px 0;
        border-radius: 8px;
        border-left: 4px solid #667eea;
    }
    
    .reasoning-item strong {
        color: #495057;
    }
    
    /* 响应式布局 */
    @media (max-width: 768px) {
        .candidate-card {
            padding: 15px;
        }
        .candidate-card h3 {
            font-size: 1.2em;
        }
        .candidate-card .score {
            font-size: 1.5em;
        }
    }
</style>
""", unsafe_allow_html=True)

st.title("RecruitFlow — 一键招聘流水线（教育机构版）")

def sanitize_single_line(text, default="未提供相关信息", limit=None):
    if text is None:
        return default
    cleaned = str(text).replace("\r", " ").replace("\n", "；")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = (
        cleaned.replace(",", "，")
        .replace(";", "；")
        .replace("|", "｜")
        .strip(" ；")
    )
    if not cleaned:
        cleaned = default
    if limit and len(cleaned) > limit:
        cleaned = cleaned[:limit].rstrip("； ，") + "..."
    return cleaned


def _clean_single_line(text, default="未提供", limit=None):
    return sanitize_single_line(text, default, limit)


def _format_highlights_for_export(row_dict):
    """
    格式化亮点标签用于导出
    优先使用Ultra格式的highlight_tags字段，确保与线上显示完全一致
    """
    tags = []
    
    # 优先使用Ultra格式的highlight_tags（列表格式）
    highlight_tags = row_dict.get("highlight_tags", [])
    
    # 处理各种可能的存储格式
    if highlight_tags is not None:
        # 如果是列表
        if isinstance(highlight_tags, list):
            tags = [str(tag).strip() for tag in highlight_tags if tag and str(tag).strip()]
        # 如果是字符串（可能被序列化了）
        elif isinstance(highlight_tags, str):
            # 尝试解析JSON字符串
            if highlight_tags.startswith("[") or highlight_tags.startswith("{"):
                try:
                    import json
                    parsed = json.loads(highlight_tags)
                    if isinstance(parsed, list):
                        tags = [str(tag).strip() for tag in parsed if tag and str(tag).strip()]
                    else:
                        # 如果不是列表，按分隔符分割
                        tags = [seg.strip() for seg in re.split(r"[｜|，,、；\s]+", highlight_tags) if seg.strip()]
                except:
                    # 解析失败，按分隔符分割
                    tags = [seg.strip() for seg in re.split(r"[｜|，,、；\s]+", highlight_tags) if seg.strip()]
            else:
                # 普通字符串，按分隔符分割
                tags = [seg.strip() for seg in re.split(r"[｜|，,、；\s]+", highlight_tags) if seg.strip()]
    
    # 如果还是没有，回退到highlights字段（字符串格式）
    if not tags:
        raw = row_dict.get("highlights", "")
        if isinstance(raw, str) and raw.strip():
            # 支持多种分隔符
            tags = [seg.strip() for seg in re.split(r"[｜|，,、；\s]+", raw) if seg.strip()]
        elif isinstance(raw, list):
            tags = [str(seg).strip() for seg in raw if str(seg).strip()]
    
    # 如果还是没有，尝试从tags字段获取
    if not tags:
        tags_field = row_dict.get("tags", [])
        if isinstance(tags_field, list):
            tags = [str(tag).strip() for tag in tags_field if str(tag).strip()]
        elif isinstance(tags_field, str):
            tags = [seg.strip() for seg in re.split(r"[｜|，,、；\s]+", tags_field) if seg.strip()]
    
    # 确保至少有标签
    if not tags:
        tags = ["综合能力"]
    
    # 返回所有标签，用|分隔（与线上显示一致）
    return "|".join(tags) if tags else "未提供"


def _safe_load_json(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


def _format_resume_summary(row_dict):
    """
    格式化简历摘要用于导出
    优先使用Ultra格式的ai_resume_summary或summary_short字段
    确保与线上显示完全一致，不截断
    """
    # 优先使用Ultra格式的字段
    summary = (
        row_dict.get("ai_resume_summary", "") or 
        row_dict.get("summary_short", "") or 
        row_dict.get("resume_mini", "") or 
        row_dict.get("summary", "") or
        ""
    )
    
    # 如果摘要为空，尝试从short_eval获取
    if not summary or summary.strip() == "":
        short_eval = row_dict.get("short_eval", "")
        if short_eval and short_eval.strip():
            summary = short_eval
    
    # 清理文本但不过度截断（移除换行和多余空格，但保留完整内容）
    if summary:
        # 只做基本清理，不截断
        cleaned = str(summary).replace("\r", " ").replace("\n", "；")
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip()
        return cleaned if cleaned else "未提供相关信息"
    
    return "未提供相关信息"


def _format_evidence_field(row_dict):
    """
    格式化证据字段用于导出
    优先使用Ultra格式的ai_review、evidence_text、strengths_reasoning_chain等字段
    确保与线上显示完全一致，不截断
    """
    # 优先使用Ultra格式的ai_review（完整的AI评价）
    ai_review = row_dict.get("ai_review", "") or row_dict.get("ai_evaluation", "")
    if ai_review and len(ai_review.strip()) > 20:
        # 如果ai_review存在且有意义，直接使用（只做基本清理，不截断）
        cleaned = str(ai_review).replace("\r", " ").replace("\n", "；")
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip()
        return cleaned if cleaned else ""
    
    # 回退到evidence_text
    evidence_text = row_dict.get("evidence_text", "")
    if evidence_text and len(evidence_text.strip()) > 20:
        cleaned = str(evidence_text).replace("\r", " ").replace("\n", "；")
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip()
        return cleaned if cleaned else ""
    
    # 尝试从推理链构建
    reasoning = _safe_load_json(row_dict.get("reasoning_chain"))
    short_eval_struct = _safe_load_json(row_dict.get("short_eval_struct"))
    
    # 尝试从Ultra格式的推理链获取
    strengths_chain = row_dict.get("strengths_reasoning_chain", {})
    weaknesses_chain = row_dict.get("weaknesses_reasoning_chain", {})
    
    # 如果是字符串，尝试解析为JSON
    if isinstance(strengths_chain, str):
        try:
            import json
            strengths_chain = json.loads(strengths_chain)
        except:
            strengths_chain = {}
    if isinstance(weaknesses_chain, str):
        try:
            import json
            weaknesses_chain = json.loads(weaknesses_chain)
        except:
            weaknesses_chain = {}
    
    def _format_strengths():
        # 优先使用Ultra格式的strengths_reasoning_chain
        if isinstance(strengths_chain, dict) and strengths_chain:
            conclusion = _clean_single_line(strengths_chain.get("conclusion"), "未命名优势", 20)
            actions = strengths_chain.get("detected_actions", [])
            actions_str = ", ".join(actions[:3]) if isinstance(actions, list) else str(actions)[:30]
            evidence = strengths_chain.get("resume_evidence", [])
            evidence_str = ", ".join(evidence[:2]) if isinstance(evidence, list) else str(evidence)[:40]
            reasoning_txt = _clean_single_line(strengths_chain.get("ai_reasoning"), "未提供", 50)
            return f"{conclusion}｜动作:{actions_str}｜证据:{evidence_str}｜推断:{reasoning_txt}"
        
        # 回退到旧格式
        chain = reasoning.get("strengths_reasoning_chain") or []
        entries = []
        for idx, item in enumerate(chain, 1):
            if not isinstance(item, dict):
                continue
            conclusion = _clean_single_line(item.get("conclusion"), "未命名优势", 18)
            actions = _clean_single_line(item.get("detected_actions"), "未提供", 24)
            evidence = _clean_single_line(item.get("resume_evidence"), "未提供", 48)
            reasoning_txt = _clean_single_line(item.get("ai_reasoning"), "未提供", 36)
            entries.append(f"{idx}. {conclusion}｜动作:{actions}｜证据:{evidence}｜推断:{reasoning_txt}")
        return "；".join(entries) if entries else "暂无可验证优势"

    def _format_weaknesses():
        # 优先使用Ultra格式的weaknesses_reasoning_chain
        if isinstance(weaknesses_chain, dict) and weaknesses_chain:
            conclusion = _clean_single_line(weaknesses_chain.get("conclusion"), "未命名劣势", 20)
            gap = weaknesses_chain.get("resume_gap", [])
            gap_str = ", ".join(gap[:2]) if isinstance(gap, list) else str(gap)[:30]
            compare = _clean_single_line(weaknesses_chain.get("compare_to_jd"), "未提供", 40)
            reasoning_txt = _clean_single_line(weaknesses_chain.get("ai_reasoning"), "未提供", 50)
            return f"{conclusion}｜缺口:{gap_str}｜JD:{compare}｜风险:{reasoning_txt}"
        
        # 回退到旧格式
        chain = reasoning.get("weaknesses_reasoning_chain") or []
        entries = []
        for idx, item in enumerate(chain, 1):
            if not isinstance(item, dict):
                continue
            conclusion = _clean_single_line(item.get("conclusion"), "未命名劣势", 18)
            gap = _clean_single_line(item.get("resume_gap"), "未提供", 32)
            compare = _clean_single_line(item.get("compare_to_jd"), "未提供", 40)
            risk = _clean_single_line(item.get("ai_reasoning"), "未提供", 36)
            entries.append(f"{idx}. {conclusion}｜缺口:{gap}｜JD:{compare}｜风险:{risk}")
        return "；".join(entries) if entries else "暂无可验证劣势"

    # 获取匹配度
    match_level = (
        row_dict.get("match_level", "") or 
        row_dict.get("match_summary", "") or
        short_eval_struct.get("match_level", "无法评估")
    )
    match_reason = short_eval_struct.get("match_reason", "未提供匹配原因")
    
    # 如果match_level为空，尝试从short_eval中提取
    if not match_level or match_level == "无法评估":
        short_eval = row_dict.get("short_eval", "")
        if "强烈推荐" in short_eval:
            match_level = "强烈推荐"
        elif "推荐" in short_eval:
            match_level = "推荐"
        elif "谨慎推荐" in short_eval:
            match_level = "谨慎推荐"
        elif "淘汰" in short_eval:
            match_level = "淘汰"
        else:
            match_level = "无法评估"
    
    match_text = f"{match_level}：{match_reason}"

    strengths_text = _format_strengths()
    weaknesses_text = _format_weaknesses()
    
    evidence_text = f"【优势】{strengths_text}【劣势】{weaknesses_text}【匹配度】{match_text}"
    
    # 只做基本清理，不截断
    if evidence_text:
        cleaned = str(evidence_text).replace("\r", " ").replace("\n", "；")
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip()
        return cleaned if cleaned else "未提供"
    
    return "未提供"


# ==================== UI 优化辅助函数 ====================
def _get_highlight_color(tag: str) -> str:
    """根据标签内容返回颜色类别（绿色/黄色/灰色）"""
    tag_lower = tag.lower()
    # 深绿色：强相关能力
    if any(keyword in tag_lower for keyword in ["沟通", "学习", "稳定", "班主任", "教学", "管理", "领导", "团队"]):
        return "green"
    # 黄色：通用优势
    elif any(keyword in tag_lower for keyword in ["客服", "电话", "活动运营", "销售", "市场", "推广"]):
        return "yellow"
    # 灰色：补充信息
    else:
        return "gray"


def _generate_summary_text(strengths_chain: list, weaknesses_chain: list) -> str:
    """前端自动生成一句话总结"""
    strengths_count = len(strengths_chain) if strengths_chain else 0
    weaknesses_count = len(weaknesses_chain) if weaknesses_chain else 0
    
    if strengths_count > weaknesses_count:
        # 提取优势关键词
        strength_keywords = []
        for item in strengths_chain[:2]:
            if isinstance(item, dict):
                conclusion = item.get("conclusion", "")
                if conclusion:
                    strength_keywords.append(conclusion)
        keywords_text = "、".join(strength_keywords[:2]) if strength_keywords else "多个方面"
        return f"✅ **推荐理由**：该候选人在 {keywords_text} 方面较为突出，整体适配度良好。"
    elif weaknesses_count > 0:
        # 提取劣势关键词
        weakness_keywords = []
        for item in weaknesses_chain[:2]:
            if isinstance(item, dict):
                conclusion = item.get("conclusion", "")
                if conclusion:
                    weakness_keywords.append(conclusion)
        keywords_text = "、".join(weakness_keywords[:2]) if weakness_keywords else "某些方面"
        return f"⚠️ **风险提示**：该候选人在 {keywords_text} 方面存在不足，建议结合岗位重点评估。"
    else:
        return "📋 **评估中**：信息不足，建议进一步了解候选人情况。"


def _create_radar_chart(scores: dict, standard_model: dict = None):
    """
    创建评分维度雷达图（支持标准模型叠加）
    
    Args:
        scores: 候选人实际得分
        standard_model: 岗位标准能力模型（可选）
    """
    # 使用文件顶部已导入的 plotly.graph_objects
    # 如果顶部导入失败，这里会抛出 NameError，需要检查 PLOTLY_AVAILABLE
    if not PLOTLY_AVAILABLE or go is None:
        raise ImportError("Plotly 未安装或导入失败。请运行: pip install plotly kaleido")
    
    categories = ["技能匹配度", "经验相关性", "成长潜力", "稳定性"]
    values = [
        float(scores.get("技能匹配度", 0)),
        float(scores.get("经验相关性", 0)),
        float(scores.get("成长潜力", 0)),
        float(scores.get("稳定性", 0)),
    ]
    
    # 添加第一个值到末尾以闭合图形
    values_closed = values + [values[0]]
    categories_closed = categories + [categories[0]]
    
    fig = go.Figure()
    
    # 如果有标准模型，先绘制标准模型（醒目颜色）
    if standard_model and isinstance(standard_model, dict):
        standard_values = [
            float(standard_model.get("skill_match", 0)),
            float(standard_model.get("experience_match", 0)),
            float(standard_model.get("growth_potential", 0)),
            float(standard_model.get("stability", 0)),
        ]
        standard_values_closed = standard_values + [standard_values[0]]
        
        # 标准模型：红色，醒目
        fig.add_trace(go.Scatterpolar(
            r=standard_values_closed,
            theta=categories_closed,
            fill='toself',
            name='岗位标准能力模型',
            line=dict(color='#ff4444', width=3, dash='dash'),
            fillcolor='rgba(255, 68, 68, 0.15)',
            opacity=0.8
        ))
    
    # 候选人实际得分：蓝色
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=categories_closed,
        fill='toself',
        name='候选人实际能力',
        line=dict(color='#1f77b4', width=2),
        fillcolor='rgba(31, 119, 180, 0.25)'
    ))
    
    # 显示图例（如果有标准模型）
    show_legend = standard_model is not None
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(size=10)
            ),
            angularaxis=dict(
                tickfont=dict(size=11)
            )
        ),
        showlegend=show_legend,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.1
        ) if show_legend else None,
        height=350,
        margin=dict(l=20, r=20, t=20, b=20)
    )
    
    return fig


def _build_export_dataframe(result_df, job_title):
    """
    构建导出DataFrame，确保与线上显示完全一致
    包含所有评分维度、AI评价、风险提示、岗位标准能力模型等字段
    """
    rows = []
    position_name = _clean_single_line(job_title, default="未提供")
    
    for idx, (_, row) in enumerate(result_df.iterrows()):
        # 将Series转换为字典，确保所有字段都被包含
        row_dict = row.to_dict()
        
        # 调试：打印关键字段（仅第一行）
        if idx == 0:
            import sys
            print(f"[DEBUG] 导出行数据（第1行）:", flush=True)
            print(f"  - highlight_tags类型: {type(row_dict.get('highlight_tags'))}, 值: {row_dict.get('highlight_tags')}", flush=True)
            print(f"  - standard_model存在: {bool(row_dict.get('standard_model'))}, 值: {row_dict.get('standard_model')}", flush=True)
            print(f"  - ai_review存在: {bool(row_dict.get('ai_review'))}, 长度: {len(str(row_dict.get('ai_review', '')))}", flush=True)
        
        candidate_id = row_dict.get("candidate_id")
        try:
            candidate_id = int(candidate_id)
        except Exception:
            candidate_id = 0
        
        # 获取各维度分数
        skill_match = int(round(float(row_dict.get("技能匹配度", row_dict.get("skill_match", 0)))))
        exp_relevance = int(round(float(row_dict.get("经验相关性", row_dict.get("experience_match", 0)))))
        growth_potential = int(round(float(row_dict.get("成长潜力", row_dict.get("growth_potential", 0)))))
        stability = int(round(float(row_dict.get("稳定性", row_dict.get("stability", 0)))))
        total_score = int(round(float(row_dict.get("总分", row_dict.get("total_score", 0)))))
        
        # 获取AI评价
        ai_evaluation = row_dict.get("ai_review", "") or row_dict.get("ai_evaluation", "") or row_dict.get("short_eval", "")
        if ai_evaluation:
            # 只做基本清理，不截断
            ai_evaluation = str(ai_evaluation).replace("\r", " ").replace("\n", "；")
            ai_evaluation = re.sub(r"\s+", " ", ai_evaluation).strip()
        
        # 获取风险提示
        risk_alert = row_dict.get("risk_alert", "")
        if not risk_alert:
            risks = row_dict.get("risks", [])
            if isinstance(risks, list) and risks:
                risk_types = [r.get("risk_type", "") if isinstance(r, dict) else str(r) for r in risks[:3] if r]
                risk_alert = "；".join(risk_types) if risk_types else "无"
            else:
                risk_alert = "无"
        if not risk_alert or risk_alert.strip() == "":
            risk_alert = "无"
        
        # 获取岗位标准能力模型
        standard_model = row_dict.get("standard_model", {})
        if isinstance(standard_model, str):
            try:
                import json
                standard_model = json.loads(standard_model)
            except:
                standard_model = {}
        
        standard_skill_match = int(round(float(standard_model.get("skill_match", standard_model.get("技能匹配度", 0)))))
        standard_exp_relevance = int(round(float(standard_model.get("experience_match", standard_model.get("经验相关性", 0)))))
        standard_growth = int(round(float(standard_model.get("growth_potential", standard_model.get("成长潜力", 0)))))
        standard_stability = int(round(float(standard_model.get("stability", standard_model.get("稳定性", 0)))))

        export_row = {
            "序号": idx + 1,  # 自动生成序号
            "姓名": _clean_single_line(row_dict.get("name"), "未提供"),
            "文件名": _clean_single_line(row_dict.get("file"), "未提供"),
            "岗位": position_name,
            "邮箱": _clean_single_line(row_dict.get("email"), "未提供"),
            "手机号": _clean_single_line(row_dict.get("phone"), "未提供"),
            "总分": total_score,
            "亮点": _format_highlights_for_export(row_dict),
            "简历摘要": _format_resume_summary(row_dict),
            "AI评价": ai_evaluation if ai_evaluation else "未提供",
            "技能匹配度": skill_match,
            "经验相关性": exp_relevance,
            "成长潜力": growth_potential,
            "稳定性": stability,
            "风险提示": risk_alert,
            "证据": _format_evidence_field(row_dict),
            "岗位标准-技能匹配度": standard_skill_match,
            "岗位标准-经验相关性": standard_exp_relevance,
            "岗位标准-成长潜力": standard_growth,
            "岗位标准-稳定性": standard_stability,
        }
        rows.append(export_row)
    
    return pd.DataFrame(rows)


with st.sidebar:
    st.header("设置")
    cfg_file = Path("backend/configs/model_config.json")
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    
    # AI配置（锁定为GPT-4）
    st.subheader("AI配置")
    st.markdown("**AI提供商：** OpenAI (已锁定)")
    st.markdown("**模型名称：** GPT-4 (已锁定)")
    st.info("🔒 AI配置已锁定为GPT-4，确保生成质量。如需修改，请联系管理员。")
    st.caption("💡 请设置环境变量: OPENAI_API_KEY 或配置 backend/configs/api_keys.json")
    
    # 固定使用GPT-4
    llm_provider = "openai"
    llm_model = "gpt-4"
    
    st.markdown("---")
    
    # 其他设置
    st.subheader("筛选设置")
    
    blind = st.toggle("盲筛模式（隐藏姓名/学校等）", value=cfg.get("blind_screen", True),
                     help="开启后，在简历筛选过程中隐藏候选人的姓名、学校等敏感信息，避免因个人背景产生偏见，确保公平筛选")
    
    thr = st.slider("置信度阈值", 0.0, 1.0, cfg.get("confidence_threshold", 0.65), 0.05,
                    help="评分置信度低于此阈值的候选人将被标记为'阈值拦截'，不会自动发送邀约。建议值：0.6-0.7。值越高，筛选越严格。")
    
    st.caption("💡 置信度阈值说明：系统会根据简历匹配度计算一个置信度分数。低于阈值的候选人需要人工审核后才能邀约。")
    if st.button("保存设置"):
        cfg["blind_screen"] = blind
        cfg["confidence_threshold"] = float(thr)
        # AI配置已锁定，不更新
        cfg["llm_provider"] = "openai"
        cfg["llm_model"] = "gpt-4"
        cfg_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        st.success("✅ 设置已保存（AI配置保持锁定为GPT-4）")
    st.markdown("---"); st.caption("版本控制")
    vm = VersionManager()
    if st.button("创建快照"):
        st.success("已创建版本：" + vm.snapshot())


init_db(); pipe = RecruitPipeline()
tab1, tab2, tab3, tab4, tab5 = st.tabs(["1 生成 JD","2 简历解析 & 匹配","3 去重 & 排序","4 邀约 & 排期","5 面试包 & 导出"])

with tab1:
    # ==========================================================
    # ✅ 统一按钮定义，防止 StreamlitDuplicateElementId 错误
    # ==========================================================
    
    # 🔹 功能：保存 JD 与 Rubric 数据
    # 🔹 修复：为按钮分配唯一 key，防止重复 ID 冲突
    # 🔹 测试结果：已通过多次 Cursor 与 Streamlit 运行验证（无异常）
    # ==========================================================
    
    # 封装按钮行为（可复用）
    def save_to_system_action():
        """统一的保存 JD + 题库操作"""
        current_bundle = st.session_state.get("ai_bundle")
        if not current_bundle:
            st.warning('请先点击"生成 JD"获得 AI 结果。')
            return
        
        try:
            job_to_save = (st.session_state.get("job_name") or "").strip()
            if not job_to_save:
                job_to_save = current_bundle.get("rubric", {}).get("job", "")
    
            pipe.save_jd(job_to_save, current_bundle["jd_long"], current_bundle["jd_short"], current_bundle["rubric"])
    
            q_path = Path("data/templates/题库示例.csv")
            rows = []
            for q in current_bundle.get("interview", []):
                points = q.get("points") or []
                points_str = "；".join(points) if isinstance(points, list) else (str(q.get("points", "")) if q.get("points") else "")
                rows.append({
                    "job": job_to_save,
                    "能力维度": q.get("dimension", "通用"),
                    "题目": q.get("question", ""),
                    "评分要点": points_str,
                    "分值": int(q.get("score", 0)),
                    "权重": round(float(q.get("score", 0)) / 100.0, 4)
                })
            if rows:
                qdf = pd.DataFrame(rows)
                q_path.parent.mkdir(parents=True, exist_ok=True)
                header = not q_path.exists()
                qdf.to_csv(q_path, mode="a", index=False, encoding="utf-8-sig", header=header)
            st.success("已写入：JD / Rubric / 题库")
        except Exception as e:
            st.error(f"❌ 写入失败：{e}")
    
    st.subheader("智能生成 JD（AI分析）")
    
    # === 新增：智能生成 JD（AI 分析） ===
    st.markdown("### 🤖 智能生成 JD（AI 分析）")
    
    # 预检查：AI Key
    key_present = bool(os.getenv("SILICONFLOW_API_KEY") or os.getenv("OPENAI_API_KEY"))
    if not key_present:
        st.warning("⚠️ 未检测到 AI Key：请在项目根目录创建 `.env` 并配置 SILICONFLOW_API_KEY。")
    
    with st.form("ai_jd_form"):
        ai_job = st.text_input("岗位名称 *", value=st.session_state.get("job_name",""), help="例如：数学竞赛教练/教学运营专员/班主任/Java后端")
        ai_must = st.text_area("必备经验/技能", value="", height=80, help="分号或空格分隔，例如：国一; LaTeX; IMO训练")
        ai_nice = st.text_area("加分项", value="", height=60, help="如：竞赛出题经验; 公开课; 内容制作")
        ai_excl = st.text_area("排除项", value="", height=60, help="如：仅实习; 兼职")
        submitted = st.form_submit_button("🚀 生成 JD", type="primary", use_container_width=True)
        
        if submitted:
            if not ai_job:
                st.error("❌ 请填写岗位名称")
            else:
                st.session_state["job_name"] = ai_job
                _update_job_meta(
                    job_name=st.session_state["job_name"],
                    must=ai_must,
                    nice=ai_nice,
                    exclude=ai_excl,
                )
                # 输入清洗：tex -> LaTeX
                ai_must = ai_must.replace("tex", "LaTeX").replace("Tex", "LaTeX")
                ai_nice = ai_nice.replace("tex", "LaTeX").replace("Tex", "LaTeX")
                try:
                    # 强制重新加载模块，确保使用最新代码
                    if 'backend.services.jd_ai' in sys.modules:
                        importlib.reload(sys.modules['backend.services.jd_ai'])
                        from backend.services.jd_ai import generate_jd_bundle
                    with st.spinner("🤖 AI正在智能分析岗位需求，生成专业JD、能力维度、面试题目，请稍候（通常需要10-30秒）..."):
                        bundle = generate_jd_bundle(ai_job, ai_must, ai_nice, ai_excl)
                        # 基于长版 JD 再做一次“短版JD提取 + 任职要求抽取能力与面试题”
                        from backend.services.jd_ai import extract_short_and_competencies_from_long_jd
                        extracted = extract_short_and_competencies_from_long_jd(bundle.get("jd_long",""), ai_job)
                        if extracted:
                            # ✅ 不再用抽取得到的短版 JD 覆盖，以免破坏“小红书风格”短版 JD
                            # 如需查看抽取版短 JD，可后续单独在前端展示 extracted["short_jd"]
                            # 用抽取得到的能力维度/面试题覆盖展示（转换为内部格式）
                            dims = []
                            for d in extracted.get("能力维度", []):
                                anchors = d.get("评分锚点") or {}
                                dims.append({
                                    "name": d.get("维度名称", ""),
                                    "weight": round(float(d.get("权重", 0)) / 100.0, 4),
                                    "desc": d.get("定义", ""),
                                    "anchors": {
                                        "20": anchors.get("20") or "基础达成：请结合 JD 中的基础要求描述。",
                                        "60": anchors.get("60") or "良好达成：能够稳定产出并不断优化。",
                                        "100": anchors.get("100") or "优秀达成：持续输出杰出成果并量化影响。",
                                    },
                                })
                            if dims:
                                bundle["dimensions"] = dims
                            qs = []
                            for q in extracted.get("能力维度_面试题", []):
                                raw_points = q.get("评分要点", [])
                                if isinstance(raw_points, str):
                                    points_list = [p.strip() for p in re.split(r"[；;、\n]", raw_points) if p.strip()]
                                else:
                                    points_list = [str(p).strip() for p in (raw_points or []) if str(p).strip()]
                                question_text = q.get("面试题", "")
                                if isinstance(question_text, list):
                                    question_text = "；".join(str(item).strip() for item in question_text if str(item).strip())
                                qs.append({
                                    "dimension": q.get("维度名称", ""),
                                    "question": question_text,
                                    "points": points_list,
                                    "score": float(q.get("分值", 0)),
                                })
                            if qs:
                                bundle["interview"] = qs
                            bundle["full_ability_list"] = construct_full_ability_list(
                                bundle.get("dimensions"), bundle.get("interview")
                            )
                    # ✅ 持久化：后续其它按钮/区域可复用
                    st.session_state["ai_bundle"] = bundle
                    st.success("✅ AI 生成完成")
                except Exception as e:
                    error_msg = str(e)
                    # 提取更友好的错误信息
                    if "Key" in error_msg or "未配置" in error_msg:
                        st.error(f"❌ {error_msg}")
                        st.info("💡 请检查项目根目录的 `.env` 文件，确保包含 SILICONFLOW_API_KEY 或 OPENAI_API_KEY，然后重启 Streamlit。")
                    elif "401" in error_msg or "403" in error_msg:
                        st.error(f"❌ API Key 验证失败：{error_msg}")
                        st.info("💡 请检查 .env 文件中的 API Key 是否正确，或是否已过期。")
                    elif "404" in error_msg or "模型" in error_msg:
                        st.error(f"❌ 模型不可用：{error_msg}")
                        st.info("💡 请检查 .env 文件中的 AI_MODEL 是否正确，或尝试更换为其他可用模型（如 Qwen2.5-32B-Instruct）。")
                    else:
                        st.error(f"❌ AI 生成失败：{error_msg}")
                        st.info("💡 系统将继续支持'离线规则版'生成，确保可用。展开下方的'AI 连接诊断'查看详细错误信息。")
    
    # 显示AI生成结果
    bundle = st.session_state.get("ai_bundle")
    if SHOW_DETAIL_SECTIONS:
        if bundle:
            st.subheader("📄 长版 JD（Boss直聘可用）")
            st.text_area("长版 JD", bundle["jd_long"], height=260)
        
            st.subheader("🪧 短版 JD（社媒/内推）")
            st.text_area("短版 JD", bundle["jd_short"], height=100)
        
            st.markdown("### 岗位能力维度与面试题目（AI分析 + AI生成）")
            full_ability = bundle.get("full_ability_list") or construct_full_ability_list(
                bundle.get("dimensions"), bundle.get("interview")
            )
            bundle["full_ability_list"] = full_ability

            display_rows = []
            for item in full_ability:
                display_rows.append({
                    "能力维度": item.get("dimension", ""),
                    "说明": item.get("description", ""),
                    "权重(%)": round(float(item.get("weight", 0.0)) * 100, 1),
                    "面试题目": item.get("question", ""),
                    "评分要点": item.get("score_points", ""),
                    "20分行为表现": item.get("score_20", ""),
                    "60分行为表现": item.get("score_60", ""),
                    "100分行为表现": item.get("score_100", ""),
                    "分值": item.get("score_value", 0.0),
                })

            df_full = pd.DataFrame(display_rows)
            st.dataframe(df_full, use_container_width=True)

            # 使用模板生成 Excel（新版本，完全基于模板）
            job_name = (st.session_state.get('job_name') or '岗位').strip()
            try:
                # 转换数据格式为 DataFrame
                dimensions_data = []
                for ability in full_ability:
                    dimensions_data.append({
                        "能力维度": ability.get("dimension", ""),
                        "说明": ability.get("description", ""),
                        "面试题目": ability.get("question", ""),
                        "评分要点": ability.get("score_points", ""),
                        "20分行为表现": ability.get("score_20", ""),
                        "60分行为表现": ability.get("score_60", ""),
                        "100分行为表现": ability.get("score_100", ""),
                        "权重": ability.get("weight", 0.0),
                    })
                
                # 创建 DataFrame（去掉控制台调试输出，避免 Windows 控制台编码导致 OSError）
                data_df = pd.DataFrame(dimensions_data)
                
                # 固定输出路径
                output_path = r"C:\RecruitFlow_Pro_MVP\docs\课程顾问_能力维度评分表(改)_输出.xlsx"
                
                def _coerce_excel_result(result, fallback_path):
                    if isinstance(result, tuple):
                        return result
                    if isinstance(result, bytes):
                        return result, fallback_path
                    read_path = result if isinstance(result, str) else fallback_path
                    with open(read_path, "rb") as f:
                        return f.read(), read_path
                
                # 使用新的导出函数（完全基于模板）
                try:
                    export_result = export_competency_excel(
                        data_df, output_path, job_title=job_name
                    )
                except TypeError:
                    print("[streamlit] export_competency_excel fallback to legacy signature")
                    export_result = export_competency_excel(data_df, output_path)

                excel_bytes, saved_path = _coerce_excel_result(export_result, output_path)

                if saved_path and saved_path != output_path:
                    st.warning(f"原始输出文件被占用，已改为保存到：`{saved_path}`")
                
                download_name = f"{job_name}_能力维度评分表.xlsx"
                st.download_button(
                    "📄 导出能力维度评分表（Excel）",
                    data=excel_bytes,
                    file_name=download_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"导出失败：{str(e)}")
                st.exception(e)
 
            # 保留单一保存入口
            if st.button("💾 写入系统（保存 JD + 题库）", type="primary", key="btn_save_rubric_1"):
                save_to_system_action()
        else:
            st.info('尚未生成 Rubric（请先点击上方"生成 JD"）')
        
        # ✅ 隐藏评分维度规则（Rubric）部分，只保留功能逻辑
        # 这里保留 bundle_for_rubric 的生成和保存逻辑，但不渲染到页面
        bundle_for_rubric = st.session_state.get("ai_bundle")
        # bundle_for_rubric 变量保留，供内部逻辑使用（如 save_to_system_action 函数中会用到）
        
        # 不再显示标题和展开块，避免 UI 重复
        # st.subheader("评分维度规则（Rubric）")  # ❌ 注释掉
        # with st.expander("评分维度规则（Rubric）", expanded=False):
        #     st.json(bundle_for_rubric["rubric"])
        
        # ✅ 仅保留一次保存按钮（上方已有的按钮 btn_save_rubric_1）
        # 因此这里删除重复按钮，防止重复显示
        # if st.button("💾 写入系统（保存 JD + 题库）", type="primary", key="btn_save_rubric_2"):
        #     save_to_system_action()
    
    # ==== AI 连接诊断（放在页面底部）====
    with st.expander("🔧 AI 连接诊断（打不开就点我）"):
        try:
            # 强制重新加载模块，避免缓存问题
            import importlib
            import sys
            if 'backend.services.ai_client' in sys.modules:
                importlib.reload(sys.modules['backend.services.ai_client'])
            from backend.services.ai_client import get_client_and_cfg, AIConfig, chat_completion
        except ImportError as e:
            st.error(f"❌ 导入 AI 客户端失败：{e}")
            st.info("💡 请检查 backend/services/ai_client.py 文件是否存在且可正常导入")
            st.stop()
        
        cfg = AIConfig()
        key_present = bool(cfg.api_key)
        st.write("**已检测到 Key：**", "✅" if key_present else "❌")
        if key_present:
            st.write("**Key 前缀：**", cfg.api_key[:10] + "..." if len(cfg.api_key) > 10 else cfg.api_key)
        st.write("**Base URL：**", cfg.base_url)
        st.write("**当前模型：**", cfg.model)
        st.write("**Temperature：**", cfg.temperature)
        
        if st.button("🧪 测试一次 AI 连通性"):
            try:
                client, cfg = get_client_and_cfg()
                with st.spinner("正在测试连接..."):
                    res = chat_completion(
                        client,
                        cfg,
                        messages=[{"role":"user","content":"只返回 OK"}],
                        temperature=0,
                        max_tokens=10
                    )
                    result = res["choices"][0]["message"]["content"].strip()
                    st.success(f"✅ AI 连通性测试成功！返回：{result}")
            except Exception as e:
                error_detail = str(e)
                st.error(f"❌ 连通性失败：{error_detail}")
                if "ChatCompletion" in error_detail or "openai>=1.0.0" in error_detail:
                    st.error("⚠️ OpenAI API 版本兼容性问题")
                    st.info("💡 这通常是因为代码中使用了旧版本的 OpenAI API。请确保：\n"
                           "1. 已安装 openai>=1.0.0：`pip install --upgrade openai`\n"
                           "2. 代码使用 `client.chat.completions.create` 而不是 `openai.ChatCompletion.create`\n"
                           "3. 重启 Streamlit 应用以清除缓存")
                    st.code("pip install --upgrade openai", language="bash")
                elif "Key" in error_detail or "未配置" in error_detail:
                    st.info("💡 检查 .env 的 Key 配置；确保文件在项目根目录；重启 Streamlit")
                elif "401" in error_detail or "403" in error_detail:
                    st.info("💡 API Key 无效或已过期，请检查 .env 中的 Key 是否正确")
                elif "404" in error_detail:
                    st.info("💡 模型不存在或未开通，请检查 .env 中的 AI_MODEL，尝试更换为 Qwen2.5-32B-Instruct")
                elif "timeout" in error_detail.lower() or "连接" in error_detail:
                    st.info("💡 网络连接问题，检查公司网络是否放行 api.siliconflow.cn；或尝试使用 OpenAI")
                else:
                    st.info("💡 检查 .env 的 Key/模型/Base URL；或公司网络是否放行 api.siliconflow.cn")
    
    # 一键启动说明
    with st.expander("🚀 一键启动程序（首次使用必看）", expanded=False):
        st.markdown("""
        ### 快速启动方法
        
        1. **最简单方式**：双击项目根目录的 `启动程序.bat` 文件
        2. **PowerShell 方式**：右键 `启动程序.ps1` -> 使用 PowerShell 运行
        3. **命令行方式**：运行 `启动程序.bat` 或 `.\\启动程序.ps1`
        
        ### 首次使用前准备
        
        - ✅ 确保已安装 Python 3.8+
        - ✅ 已创建虚拟环境：`python -m venv .venv`
        - ✅ 已安装依赖：`.venv\\Scripts\\pip install -r requirements.txt`
        - ✅ 已配置 `.env` 文件（AI Key 等，可选）
        
        ### 详细使用说明
        
        请查看项目根目录的 `使用说明.md` 文件，包含：
        - 📋 完整功能说明
        - 🔧 常见问题解答
        - 🎯 各功能模块使用指南
        
        ### 当前运行状态
        
        - 🌐 访问地址：http://localhost:8501
        - 📁 项目目录：""" + str(Path.cwd()) + """
        """)
        
        # 显示启动脚本路径
        bat_path = Path.cwd() / "启动程序.bat"
        ps1_path = Path.cwd() / "启动程序.ps1"
        
        if bat_path.exists():
            st.success(f"✅ 启动脚本已找到：`{bat_path}`")
        else:
            st.warning(f"⚠️ 启动脚本不存在：`{bat_path}`")
        
        if ps1_path.exists():
            st.success(f"✅ PowerShell 脚本已找到：`{ps1_path}`")
        
        # 提供快速命令
        cmd_text = f"""# 快速启动命令（复制到命令行运行）
cd "{Path.cwd()}"
.venv\\Scripts\\python.exe -m streamlit run app/streamlit_app.py --server.port 8501"""
        st.code(cmd_text, language="bash")
    
    st.markdown("---")
    if SHOW_OFFLINE_SECTION:
        st.markdown("---")
        st.markdown("### 📋 离线规则版（备用）")
        
        # 重新读取配置（因为可能在侧边栏已更新）
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        use_ai = cfg.get("llm_provider") in ["openai", "claude", "siliconflow"]
        
        # 输入表单（离线版）
        with st.form("jd_generation_form"):
            col1, col2 = st.columns(2)
            with col1:
                job_name = st.text_input("岗位名称 *", placeholder="例如：数据分析师、产品经理、运营专员等", 
                                        value=st.session_state.get("job_name", ""))
            with col2:
                st.caption("💡 必填项")
            
            must_have = st.text_area("必备经验/技能", placeholder="例如：3年以上数据分析经验；熟悉Python、SQL；有教育行业背景", 
                                    height=80, help="用分号(;)分隔多个技能")
            nice_to_have = st.text_area("加分项", placeholder="例如：熟悉机器学习；有团队管理经验；数据可视化能力强", 
                                       height=80, help="用分号(;)分隔多个加分项")
            exclude_keywords = st.text_area("排除项", placeholder="例如：频繁跳槽；仅实习经验；外包经历", 
                                           height=60, help="用分号(;)分隔多个排除关键词")
            
            submitted = st.form_submit_button("🚀 生成 JD", type="primary", use_container_width=True)
        
        # 处理生成请求
        if submitted:
            if not job_name:
                st.error("❌ 请填写岗位名称")
            else:
                st.session_state["job_name"] = job_name
                _update_job_meta(
                    job_name=job_name,
                    must=must_have,
                    nice=nice_to_have,
                    exclude=exclude_keywords,
                )
                with st.spinner("🤖 AI正在智能分析岗位需求，生成专业JD、能力维度、面试题目，请稍候（通常需要10-30秒）..."):
                    try:
                        jd_long, jd_short, rubric, interview_questions = pipe.generate_jd(
                            job_name, must_have=must_have, nice_to_have=nice_to_have, 
                            exclude_keywords=exclude_keywords, use_ai=use_ai
                        )
                        st.session_state["jd_result"] = (jd_long, jd_short, rubric, interview_questions)
                        st.success("✅ AI生成成功！")
                    except Exception as e:
                        st.error(f"❌ 生成失败: {str(e)}")
                        if use_ai:
                            st.info("正在尝试使用离线模式...")
                            try:
                                jd_long, jd_short, rubric, interview_questions = pipe.generate_jd(
                                    job_name, must_have=must_have, nice_to_have=nice_to_have, 
                                    exclude_keywords=exclude_keywords, use_ai=False
                                )
                                st.session_state["jd_result"] = (jd_long, jd_short, rubric, interview_questions)
                                st.success("✅ 离线模式生成成功")
                            except Exception as e2:
                                st.error(f"❌ 离线模式也失败: {str(e2)}")
        
        # 显示结果
        if "jd_result" in st.session_state:
            jd_long, jd_short, rubric, interview_questions = st.session_state["jd_result"]
            
            # 长版JD
            st.markdown("### 📄 长版 JD（Boss直聘可用）")
            st.text_area("", jd_long, height=300, key="jd_long_display", label_visibility="collapsed")
            
            # 短版JD
            st.markdown("### ✨ 短版 JD（社媒/内推）")
            st.text_area("", jd_short, height=100, key="jd_short_display", label_visibility="collapsed")
            
            # 能力维度
            st.markdown("### 🎯 岗位能力维度（AI分析）")
            if rubric.get("dimensions"):
                dim_data = []
                for dim in rubric["dimensions"]:
                    weight = float(dim.get("weight", 0))
                    dim_data.append({
                        "能力维度": dim.get("name", ""),
                        "权重": f"{weight * 100:.1f}%",
                        "说明": dim.get("description", "")
                    })
                dim_df = pd.DataFrame(dim_data)
                st.dataframe(dim_df, use_container_width=True)
            else:
                st.info('尚未生成 Rubric（请先点击上方"生成 JD"）')
            
            # 面试题目
            st.markdown("### 💬 面试题目和评分标准（AI生成）")
            if interview_questions and interview_questions.get("questions"):
                for idx, q in enumerate(interview_questions["questions"], 1):
                    weight_pct = float(q.get('weight', 0)) * 100
                    with st.expander(f"题目 {idx}: {q.get('dimension', '通用')} - 权重: {weight_pct:.0f}%"):
                        st.markdown(f"**问题：** {q.get('question', '')}")
                        st.markdown(f"**评分标准：** {q.get('evaluation_criteria', '')}")
                        if q.get('weight'):
                            st.caption(f"权重: {float(q.get('weight', 0)) * 100:.0f}%")
            else:
                st.info("暂无面试题目")
            
            # 保存按钮
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("💾 保存 JD & 评分维度", type="primary", key="btn_save_jd_score"):
                    pipe.save_jd(job_name, jd_long, jd_short, rubric, interview_questions)
                    st.success("✅ 已保存")

with tab2:
    st.subheader("导入简历（CSV/TXT 示例）并匹配打分")
    uploaded = st.file_uploader("上传简历 CSV（见 data/samples/sample_resumes.csv）或 TXT（单个）", type=["csv","txt"], accept_multiple_files=True)
    if uploaded:
        for f in uploaded:
            if f.name.endswith(".csv"):
                df = pd.read_csv(f); pipe.ingest_resumes_df(df)
            else:
                txt = f.read().decode("utf-8", errors="ignore"); pipe.ingest_text_resume(txt)
        st.success("已导入")
    if st.button("批量评分"):
        start = time.time()
        result_df = pipe.score_all(st.session_state.get("job_name"))
        if st.session_state.get("job_name"):
            _update_job_meta(job_name=st.session_state.get("job_name"))
        st.session_state["scored"] = result_df
        st.info(f"评分完成，用时 {time.time()-start:.2f} s")
        # 汉化显示
        result_df_display = translate_dataframe_columns(result_df)
        st.dataframe(result_df_display, use_container_width=True)

    st.markdown("---")
    st.markdown("## 🤖 AI 智能匹配（批量上传 PDF/DOCX/图片）")

    jd_text = ""
    if st.session_state.get("ai_bundle") and st.session_state["ai_bundle"].get("jd_long"):
        jd_text = st.session_state["ai_bundle"]["jd_long"]

    jd_text = st.text_area(
        "岗位 JD 文本（已自动带入 AI 长版 JD，可手动编辑）",
        value=jd_text,
        height=200,
        help="AI 会基于这里的 JD 与简历进行匹配，请确保内容准确。"
    )

    uploaded_files = st.file_uploader(
        "上传多份简历（支持：pdf、docx、txt、jpg、jpeg、png）",
        type=["pdf", "docx", "txt", "jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="ai_resume_uploader"
    )

    if uploaded_files:
        with st.spinner("正在解析简历文件…"):
            resumes_df = parse_uploaded_files_to_df(uploaded_files)
        if resumes_df.empty:
            st.warning("没有解析到有效简历，请检查文件格式。")
        else:
            st.success(f"已解析 {len(resumes_df)} 份简历。")
            base_columns = ["candidate_id", "name", "file", "email", "phone", "text_len"]
            for col in base_columns:
                if col not in resumes_df.columns:
                    if col == "candidate_id":
                        resumes_df[col] = range(1, len(resumes_df) + 1)
                    elif col == "text_len":
                        resumes_df[col] = resumes_df.get("resume_text", "").apply(lambda x: len(str(x)) if x else 0)
                    else:
                        resumes_df[col] = ""
            # 使用字段映射翻译列名
            display_resumes_df = resumes_df[base_columns].copy()
            display_resumes_df = translate_dataframe_columns(display_resumes_df)
            st.dataframe(
                display_resumes_df,
                use_container_width=True
            )

            if st.button("🚀 用 AI 批量匹配并打分"):
                if not jd_text.strip():
                    st.warning("请先填写/粘贴岗位 JD。")
                else:
                    # 获取岗位名称，用于岗位级清洗逻辑
                    job_title = st.session_state.get("job_name", "")
                    if job_title:
                        _update_job_meta(job_name=job_title)
                    # 添加日志查看器（用于调试）
                    with st.expander("🔍 调试日志（点击查看后端日志）", expanded=False):
                        st.info("💡 Python的print()输出在运行Streamlit的终端/控制台中，不在浏览器控制台。")
                        st.info("💡 请查看启动Streamlit的终端窗口，应该能看到 [DEBUG] 开头的日志。")
                        st.code("""
示例日志格式：
[DEBUG] ai_match_resumes_df_ultra: 开始批量匹配，共2份简历
[DEBUG] 简历1/2: 开始评分，文本长度=XXX
[DEBUG] Ultra引擎.score() 开始: resume_length=XXX
[DEBUG] S2: 开始动作识别...
[DEBUG] S9: 构建证据链完成，evidence_chain数量=X
[DEBUG] 简历1/2: 评分完成，ai_review=True, highlight_tags=X
                        """, language="text")
                    
                    with st.spinner("AI 正在智能分析匹配度（Ultra引擎），请稍候…"):
                        # 优先使用Ultra版评分引擎
                        scored_df = None
                        try:
                            scored_df = ai_match_resumes_df_ultra(jd_text, resumes_df, job_title)
                        except Exception as e:
                            import traceback
                            error_trace = traceback.format_exc()
                            st.error(f"❌ Ultra引擎异常: {str(e)}")
                            with st.expander("查看详细错误信息"):
                                st.code(error_trace, language="python")
                            st.warning(f"Ultra引擎失败，回退到标准版本: {str(e)[:100]}")
                        
                        # 只有在Ultra引擎失败时才使用标准版本
                        if scored_df is None or scored_df.empty:
                            scored_df = ai_match_resumes_df(jd_text, resumes_df, job_title)
                    # 确保所有必需字段存在（优先使用Ultra字段，兼容旧字段）
                    score_columns = [
                        "candidate_id",
                        "name",
                        "file",
                        "email",
                        "phone",
                        "总分",
                        "技能匹配度",
                        "经验相关性",
                        "成长潜力",
                        "稳定性",
                        "score_explain",
                        "short_eval",
                        "highlights",
                        "resume_mini",
                        "证据",
                    ]
                    for col in score_columns:
                        if col not in scored_df.columns:
                            if col == "candidate_id":
                                scored_df[col] = range(1, len(scored_df) + 1)
                            else:
                                scored_df[col] = ""
                    
                    # 确保Ultra字段映射到兼容字段（用于列表页显示）
                    # 如果兼容字段为空，从Ultra字段填充
                    if "short_eval" in scored_df.columns:
                        mask = scored_df["short_eval"].isna() | (scored_df["short_eval"] == "")
                        # 检查 ai_review 列是否存在
                        if "ai_review" in scored_df.columns:
                            scored_df.loc[mask, "short_eval"] = scored_df.loc[mask, "ai_review"].fillna("")
                        elif "ai_evaluation" in scored_df.columns:
                            scored_df.loc[mask, "short_eval"] = scored_df.loc[mask, "ai_evaluation"].fillna("")
                    
                    if "highlights" in scored_df.columns:
                        mask = scored_df["highlights"].isna() | (scored_df["highlights"] == "")
                        # 从highlight_tags列表转为字符串
                        def format_highlights(row):
                            highlight_tags = row.get("highlight_tags")
                            # 安全检查：处理各种数据类型（避免空数组的歧义）
                            try:
                                # 如果是列表且不为空
                                if isinstance(highlight_tags, list) and len(highlight_tags) > 0:
                                    tags = [str(tag) for tag in highlight_tags if tag]
                                    if tags:
                                        return " | ".join(tags)
                                # 如果是numpy数组或其他可迭代对象
                                elif highlight_tags is not None and hasattr(highlight_tags, '__iter__') and not isinstance(highlight_tags, str):
                                    try:
                                        # 尝试转换为列表
                                        tags_list = list(highlight_tags)
                                        if len(tags_list) > 0:
                                            tags = [str(tag) for tag in tags_list if tag]
                                            if tags:
                                                return " | ".join(tags)
                                    except (TypeError, ValueError):
                                        pass
                                # 如果是字符串
                                elif isinstance(highlight_tags, str) and highlight_tags.strip():
                                    return highlight_tags
                            except Exception:
                                pass
                            
                            # 回退到highlights字段
                            highlights_val = row.get("highlights", "")
                            if isinstance(highlights_val, str) and highlights_val.strip():
                                return highlights_val
                            elif isinstance(highlights_val, list) and len(highlights_val) > 0:
                                tags = [str(tag) for tag in highlights_val if tag]
                                return " | ".join(tags) if tags else ""
                            return ""
                        scored_df.loc[mask, "highlights"] = scored_df.loc[mask].apply(format_highlights, axis=1)
                    
                    if "resume_mini" in scored_df.columns:
                        mask = scored_df["resume_mini"].isna() | (scored_df["resume_mini"] == "")
                        # 检查 ai_resume_summary 列是否存在
                        if "ai_resume_summary" in scored_df.columns:
                            scored_df.loc[mask, "resume_mini"] = scored_df.loc[mask, "ai_resume_summary"].fillna("")
                        elif "summary_short" in scored_df.columns:
                            scored_df.loc[mask, "resume_mini"] = scored_df.loc[mask, "summary_short"].fillna("")
                    
                    if "证据" in scored_df.columns:
                        mask = scored_df["证据"].isna() | (scored_df["证据"] == "")
                        # 检查 evidence_text 列是否存在
                        if "evidence_text" in scored_df.columns:
                            scored_df.loc[mask, "证据"] = scored_df.loc[mask, "evidence_text"].fillna("")
                    
                    result_df = scored_df
                    
                    # 调试：检查推理链字段是否在DataFrame中
                    if not result_df.empty:
                        sample_row = result_df.iloc[0]
                        print(f"[DEBUG] 前端DataFrame检查: 列数={len(result_df.columns)}, 行数={len(result_df)}", flush=True)
                        print(f"[DEBUG] 前端DataFrame列名: {list(result_df.columns)[:20]}...", flush=True)
                        if "strengths_reasoning_chain" in result_df.columns:
                            sample_strengths = sample_row.get("strengths_reasoning_chain", {})
                            print(f"[DEBUG] 前端DataFrame中strengths_reasoning_chain存在: type={type(sample_strengths)}, value={sample_strengths if isinstance(sample_strengths, dict) else 'N/A'}", flush=True)
                        else:
                            print(f"[DEBUG] 前端DataFrame中strengths_reasoning_chain不存在！", flush=True)
                        if "weaknesses_reasoning_chain" in result_df.columns:
                            sample_weaknesses = sample_row.get("weaknesses_reasoning_chain", {})
                            print(f"[DEBUG] 前端DataFrame中weaknesses_reasoning_chain存在: type={type(sample_weaknesses)}, value={sample_weaknesses if isinstance(sample_weaknesses, dict) else 'N/A'}", flush=True)
                        else:
                            print(f"[DEBUG] 前端DataFrame中weaknesses_reasoning_chain不存在！", flush=True)
                    
                    display_columns = [
                        "candidate_id",
                        "name",
                        "file",
                        "总分",
                        "技能匹配度",
                        "经验相关性",
                        "成长潜力",
                        "稳定性",
                        "short_eval",
                        "highlights",
                        "resume_mini",
                        "证据",
                    ]
                    existing_display = [col for col in display_columns if col in result_df.columns]
                    if existing_display:
                        display_df = result_df[existing_display].copy()
                        if "resume_mini" in display_df.columns:
                            display_df["resume_mini"] = display_df["resume_mini"].apply(
                                lambda x: (x[:80] + "…") if isinstance(x, str) and len(x) > 80 else x
                            )
                        display_df = translate_dataframe_columns(display_df)
                    st.dataframe(
                            display_df,
                            use_container_width=True,
                            hide_index=True,
                        )
                    export_job_title = st.session_state.get("job_name") or job_title or "未提供"
                    export_df = _build_export_dataframe(result_df, export_job_title)

                    st.markdown("### 候选人洞察详情")
                    # 按总分排序（高分在前）
                    result_df_sorted = result_df.sort_values(by="总分", ascending=False).reset_index(drop=True)
                    for _, row in result_df_sorted.iterrows():
                        candidate_name = row.get('name', '匿名候选人')
                        score_label = row.get("总分")
                        score_value = float(score_label) if score_label is not None else 0
                        
                        # ========== Accordion 标题：显示姓名和总分 ==========
                        expander_title = f"👤 {candidate_name} ｜ 总分：{score_value:.1f}"
                        
                        # ========== 用 st.expander 包裹所有内容，默认折叠 ==========
                        with st.expander(expander_title, expanded=False):
                            # ========== 1. 顶部概览卡片 ==========
                            st.markdown(f"""
                            <div class="candidate-card">
                                <h3>{candidate_name}</h3>
                                <div class="score">总分：{score_value:.1f}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # ========== Ultra字段接入：亮点标签 ==========
                            # 优先使用Ultra字段 highlight_tags（列表格式）
                            highlight_tags_ultra = row.get("highlight_tags", [])
                            
                            # 调试：检查字段类型和内容
                            if "highlight_tags" in row:
                                print(f"[DEBUG] highlight_tags类型: {type(highlight_tags_ultra)}, 值: {highlight_tags_ultra}")
                            
                            if highlight_tags_ultra and isinstance(highlight_tags_ultra, list) and len(highlight_tags_ultra) > 0:
                                # Ultra字段：直接使用列表
                                highlights_raw = [str(tag).strip() for tag in highlight_tags_ultra if tag and str(tag).strip()]
                            else:
                                # 回退：从highlights字符串解析
                                highlights_str = row.get("highlights", "")
                                if isinstance(highlights_str, str) and highlights_str.strip():
                                    highlights_raw = [tag.strip() for tag in re.split(r"[｜|，,、\s]+", highlights_str) if tag.strip()]
                                elif isinstance(highlights_str, list):
                                    highlights_raw = [str(tag).strip() for tag in highlights_str if tag and str(tag).strip()]
                                else:
                                    highlights_raw = []
                            
                            # 调试：输出最终结果
                            if not highlights_raw:
                                print(f"[DEBUG] 亮点标签为空，row中的字段: {list(row.keys())}")
                                print(f"[DEBUG] highlight_tags={row.get('highlight_tags')}, highlights={row.get('highlights')}")
                            
                            # 生成亮点标签HTML（圆角标签样式）
                            if highlights_raw:
                                st.markdown("**🏷️ 亮点标签**")
                                highlight_html = '<div style="margin: 10px 0; display: flex; flex-wrap: wrap; gap: 8px;">'
                                for tag in highlights_raw:
                                    color_class = _get_highlight_color(tag)
                                    highlight_html += f'<span class="highlight-tag highlight-tag-{color_class}" style="display: inline-block; padding: 6px 12px; margin: 0; border-radius: 16px; font-size: 0.9em; font-weight: 500; color: white; background-color: {"#28a745" if color_class == "green" else "#ffc107" if color_class == "yellow" else "#6c757d"};">{tag}</span>'
                                highlight_html += '</div>'
                                st.markdown(highlight_html, unsafe_allow_html=True)
                            else:
                                st.markdown("**🏷️ 亮点标签**")
                                st.caption("暂无亮点标签")
                            
                            # ========== Ultra字段接入：简历摘要（三行结构化）==========
                            # 优先使用Ultra字段 ai_resume_summary 或 summary_short
                            ai_resume_summary = row.get("ai_resume_summary", "")
                            summary_short = row.get("summary_short", "")
                            
                            # 优先使用 ai_resume_summary（Ultra格式）
                            resume_summary_text = ai_resume_summary or summary_short
                            
                            if resume_summary_text:
                                st.markdown("**📄 简历摘要**")
                                # 如果是三行结构化格式（包含换行符），按行显示
                                if '\n' in resume_summary_text:
                                    summary_lines = [line.strip() for line in resume_summary_text.split('\n') if line.strip()]
                                    summary_html = '<div class="resume-mini" style="line-height: 1.8;">'
                                    for i, line in enumerate(summary_lines[:3], 1):
                                        summary_html += f'<div style="margin-bottom: 8px;">{i}. {line}</div>'
                                    summary_html += '</div>'
                                    st.markdown(summary_html, unsafe_allow_html=True)
                                else:
                                    # 普通文本格式
                                    st.markdown(f'<div class="resume-mini">{resume_summary_text}</div>', unsafe_allow_html=True)
                            else:
                                # 回退到兼容字段
                                resume_mini = row.get("resume_mini", "")
                                if resume_mini:
                                    st.markdown("**📄 简历摘要**")
                                    st.markdown(f'<div class="resume-mini">{resume_mini}</div>', unsafe_allow_html=True)
                                else:
                                    st.markdown("**📄 简历摘要**")
                                    st.caption("暂无短版简历")
                            
                            # ========== Ultra字段接入：AI评价（三段式格式）==========
                            # 优先使用Ultra字段 ai_review，其次 ai_evaluation
                            ai_review = row.get("ai_review", "")
                            ai_evaluation = row.get("ai_evaluation", "")
                            
                            # 调试：检查字段
                            if not ai_review and not ai_evaluation:
                                print(f"[DEBUG] AI评价为空，row中的字段: {list(row.keys())}")
                                print(f"[DEBUG] ai_review={ai_review}, ai_evaluation={ai_evaluation}, short_eval={row.get('short_eval')}")
                            
                            # 优先使用 ai_review（Ultra格式）
                            ai_review_text = ai_review or ai_evaluation
                            
                            if ai_review_text:
                                st.markdown("**🤖 AI 评价**")
                                # 解析三段式结构
                                evidence_match = re.search(r'【证据】\s*(.*?)(?=【推理】|【结论】|$)', ai_review_text, re.DOTALL)
                                reasoning_match = re.search(r'【推理】\s*(.*?)(?=【结论】|$)', ai_review_text, re.DOTALL)
                                conclusion_match = re.search(r'【结论】\s*(.*?)$', ai_review_text, re.DOTALL)
                                
                                if evidence_match or reasoning_match or conclusion_match:
                                    # 三段式格式化显示
                                    eval_html = '<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff; line-height: 1.8;">'
                                    if evidence_match:
                                        evidence_text = evidence_match.group(1).strip()
                                        eval_html += f'<div style="margin-bottom: 12px;"><strong style="color: #007bff;">【证据】</strong><div style="margin-top: 6px; padding-left: 12px;">{evidence_text}</div></div>'
                                    if reasoning_match:
                                        reasoning_text = reasoning_match.group(1).strip()
                                        eval_html += f'<div style="margin-bottom: 12px;"><strong style="color: #28a745;">【推理】</strong><div style="margin-top: 6px; padding-left: 12px;">{reasoning_text}</div></div>'
                                    if conclusion_match:
                                        conclusion_text = conclusion_match.group(1).strip()
                                        eval_html += f'<div><strong style="color: #dc3545;">【结论】</strong><div style="margin-top: 6px; padding-left: 12px;">{conclusion_text}</div></div>'
                                    eval_html += '</div>'
                                    st.markdown(eval_html, unsafe_allow_html=True)
                                else:
                                    # 普通格式显示
                                    st.markdown(f'<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff; line-height: 1.6; white-space: pre-wrap;">{ai_review_text}</div>', unsafe_allow_html=True)
                            else:
                                st.markdown("**🤖 AI 评价**")
                                st.caption("暂无AI评价")
                            
                            st.markdown("---")
                            
                            # ========== 2. 从Ultra Format读取优势/劣势推理链 ==========
                            # 优先使用Ultra-Format标准字段
                            strengths_reasoning_chain = row.get("strengths_reasoning_chain", {})
                            weaknesses_reasoning_chain = row.get("weaknesses_reasoning_chain", {})
                            
                            # 调试：输出字段类型和基本信息
                            try:
                                strengths_type = type(strengths_reasoning_chain).__name__
                                weaknesses_type = type(weaknesses_reasoning_chain).__name__
                                print(f"[DEBUG] 前端读取推理链: strengths类型={strengths_type}, weaknesses类型={weaknesses_type}", flush=True)
                            except Exception as e:
                                print(f"[DEBUG] 前端读取推理链: 类型检查失败: {str(e)[:50]}", flush=True)
                            if isinstance(strengths_reasoning_chain, dict):
                                print(f"[DEBUG]   strengths字段: conclusion={bool(strengths_reasoning_chain.get('conclusion'))}, ai_reasoning={bool(strengths_reasoning_chain.get('ai_reasoning'))}", flush=True)
                            elif isinstance(strengths_reasoning_chain, str):
                                print(f"[DEBUG]   strengths字段是字符串，长度={len(strengths_reasoning_chain)}", flush=True)
                            if isinstance(weaknesses_reasoning_chain, dict):
                                print(f"[DEBUG]   weaknesses字段: conclusion={bool(weaknesses_reasoning_chain.get('conclusion'))}, ai_reasoning={bool(weaknesses_reasoning_chain.get('ai_reasoning'))}", flush=True)
                            elif isinstance(weaknesses_reasoning_chain, str):
                                print(f"[DEBUG]   weaknesses字段是字符串，长度={len(weaknesses_reasoning_chain)}", flush=True)
                            
                            # 调试：检查推理链字段
                            if not strengths_reasoning_chain or (isinstance(strengths_reasoning_chain, dict) and not strengths_reasoning_chain.get("conclusion") and not strengths_reasoning_chain.get("ai_reasoning")):
                                try:
                                    conclusion = strengths_reasoning_chain.get("conclusion", "") if isinstance(strengths_reasoning_chain, dict) else ""
                                    print(f"[DEBUG] 优势推理链为空或无效: conclusion={conclusion[:50] if conclusion else 'None'}", flush=True)
                                except Exception as e:
                                    print(f"[DEBUG] 优势推理链为空或无效: {str(e)[:50]}", flush=True)
                            if not weaknesses_reasoning_chain or (isinstance(weaknesses_reasoning_chain, dict) and not weaknesses_reasoning_chain.get("conclusion") and not weaknesses_reasoning_chain.get("ai_reasoning")):
                                try:
                                    conclusion = weaknesses_reasoning_chain.get("conclusion", "") if isinstance(weaknesses_reasoning_chain, dict) else ""
                                    print(f"[DEBUG] 劣势推理链为空或无效: conclusion={conclusion[:50] if conclusion else 'None'}", flush=True)
                                except Exception as e:
                                    print(f"[DEBUG] 劣势推理链为空或无效: {str(e)[:50]}", flush=True)
                            
                            # 转换为列表格式（用于前端显示）
                            strengths_chain = []
                            weaknesses_chain = []
                            
                            # 处理优势推理链
                            # 检查是否是字符串（可能被序列化了）
                            if isinstance(strengths_reasoning_chain, str):
                                try:
                                    import json
                                    strengths_reasoning_chain = json.loads(strengths_reasoning_chain)
                                    print(f"[DEBUG] 优势推理链被序列化为字符串，已解析", flush=True)
                                except:
                                    print(f"[DEBUG] 优势推理链是字符串但无法解析: {strengths_reasoning_chain[:100]}", flush=True)
                                    strengths_reasoning_chain = {}
                            
                            if strengths_reasoning_chain and isinstance(strengths_reasoning_chain, dict):
                                # Ultra-Format: {conclusion, detected_actions, resume_evidence, ai_reasoning}
                                conclusion = strengths_reasoning_chain.get("conclusion", "")
                                detected_actions = strengths_reasoning_chain.get("detected_actions", [])
                                resume_evidence = strengths_reasoning_chain.get("resume_evidence", [])
                                ai_reasoning = strengths_reasoning_chain.get("ai_reasoning", "")
                                
                                print(f"[DEBUG] 前端处理优势推理链: conclusion={conclusion[:50] if conclusion else 'None'}, ai_reasoning长度={len(ai_reasoning)}", flush=True)
                                
                                # 只要有conclusion或ai_reasoning，就认为有内容
                                if conclusion or ai_reasoning or detected_actions or resume_evidence:
                                    strengths_chain.append({
                                        "conclusion": conclusion or "具备岗位所需的核心能力",
                                        "detected_actions": ", ".join(detected_actions[:3]) if isinstance(detected_actions, list) and detected_actions else "",
                                        "resume_evidence": ", ".join(resume_evidence[:3]) if isinstance(resume_evidence, list) and resume_evidence else "",
                                        "ai_reasoning": ai_reasoning or "基于评分结果，候选人具备一定的工作能力。"
                                    })
                                    print(f"[DEBUG] 优势推理链已添加到strengths_chain，当前长度={len(strengths_chain)}", flush=True)
                                else:
                                    print(f"[DEBUG] 优势推理链内容为空，未添加到strengths_chain", flush=True)
                            else:
                                print(f"[DEBUG] 优势推理链不存在或格式错误: type={type(strengths_reasoning_chain)}", flush=True)
                            
                            # 处理劣势推理链
                            # 如果weaknesses_reasoning_chain是字符串，尝试解析为JSON
                            if isinstance(weaknesses_reasoning_chain, str):
                                try:
                                    import json
                                    weaknesses_reasoning_chain = json.loads(weaknesses_reasoning_chain)
                                except:
                                    weaknesses_reasoning_chain = {}
                            
                            if weaknesses_reasoning_chain and isinstance(weaknesses_reasoning_chain, dict):
                                # Ultra-Format: {conclusion, resume_gap, compare_to_jd, ai_reasoning}
                                conclusion = weaknesses_reasoning_chain.get("conclusion", "")
                                resume_gap = weaknesses_reasoning_chain.get("resume_gap", [])
                                compare_to_jd = weaknesses_reasoning_chain.get("compare_to_jd", "")
                                ai_reasoning = weaknesses_reasoning_chain.get("ai_reasoning", "")
                                
                                print(f"[DEBUG] 前端处理劣势推理链: conclusion={conclusion}, ai_reasoning长度={len(ai_reasoning)}", flush=True)
                                
                                # 只要有conclusion或ai_reasoning，就认为有内容
                                if conclusion or ai_reasoning or resume_gap or compare_to_jd:
                                    weaknesses_chain.append({
                                        "conclusion": conclusion or "存在一定不足",
                                        "resume_gap": ", ".join(resume_gap[:3]) if isinstance(resume_gap, list) and resume_gap else "",
                                        "compare_to_jd": compare_to_jd or "",
                                        "ai_reasoning": ai_reasoning or "基于评分结果，候选人存在一定不足，建议进一步评估。"
                                    })
                                    print(f"[DEBUG] 劣势推理链已添加到weaknesses_chain，当前长度={len(weaknesses_chain)}", flush=True)
                                else:
                                    print(f"[DEBUG] 劣势推理链内容为空，未添加到weaknesses_chain", flush=True)
                            else:
                                print(f"[DEBUG] 劣势推理链类型错误或为空: type={type(weaknesses_reasoning_chain)}, value={weaknesses_reasoning_chain}", flush=True)
                            
                            # 如果Ultra-Format字段为空，从evidence_chains生成（兼容逻辑）
                            if not strengths_chain and not weaknesses_chain:
                                evidence_chains_ultra = row.get("evidence_chains", {})
                                
                                # 生成优势推理链（从evidence_chains中挑选最强的2条）
                                if evidence_chains_ultra and isinstance(evidence_chains_ultra, dict):
                                    # 优先从技能匹配度和经验相关性中提取
                                    skill_evidences = evidence_chains_ultra.get("技能匹配度", [])
                                    exp_evidences = evidence_chains_ultra.get("经验相关性", [])
                                    
                                    # 确保是列表格式
                                    if not isinstance(skill_evidences, list):
                                        skill_evidences = []
                                    if not isinstance(exp_evidences, list):
                                        exp_evidences = []
                                    
                                    for ev in (skill_evidences + exp_evidences)[:2]:
                                        if isinstance(ev, dict):
                                            strengths_chain.append({
                                                "action": ev.get("action", ""),
                                                "evidence": ev.get("evidence", ""),
                                                "reasoning": ev.get("reasoning", "")
                                            })
                                
                                # 生成劣势推理链（从weak_points或evidence_chains中提取）
                                weak_points = row.get("weak_points", [])
                                if weak_points and isinstance(weak_points, list) and len(weak_points) > 0:
                                    # weak_points是字符串列表，转换为推理链格式
                                    for point in weak_points[:2]:
                                        if isinstance(point, str):
                                            weaknesses_chain.append({
                                                "action": "短板项",
                                                "evidence": point,
                                                "reasoning": point
                                            })
                                elif evidence_chains_ultra and isinstance(evidence_chains_ultra, dict):
                                    # 从evidence_chains中找出最低分维度
                                    score_dims = row.get("score_dims", {})
                                    if score_dims and isinstance(score_dims, dict):
                                        dim_scores = {
                                            "技能匹配度": score_dims.get("skill_match", 0),
                                            "经验相关性": score_dims.get("experience_match", 0),
                                            "成长潜力": score_dims.get("growth_potential", 0),
                                            "稳定性": score_dims.get("stability", 0),
                                        }
                                        lowest_dim = min(dim_scores.items(), key=lambda x: x[1])[0]
                                        lowest_evidences = evidence_chains_ultra.get(lowest_dim, [])
                                        
                                        if isinstance(lowest_evidences, list):
                                            for ev in lowest_evidences[:2]:
                                                if isinstance(ev, dict):
                                                    weaknesses_chain.append({
                                                        "action": ev.get("action", ""),
                                                        "evidence": ev.get("evidence", ""),
                                                        "reasoning": ev.get("reasoning", "")
                                                    })
                            
                            # 兼容旧格式推理链（最后回退）
                            if not strengths_chain and not weaknesses_chain:
                                reasoning_raw = row.get("reasoning_chain") or {}
                                try:
                                    reasoning_obj = (
                                        json.loads(reasoning_raw)
                                        if isinstance(reasoning_raw, str)
                                        else reasoning_raw
                                    )
                                except Exception:
                                    reasoning_obj = {}
                                
                                old_strengths = reasoning_obj.get("strengths_reasoning_chain") or []
                                old_weaknesses = reasoning_obj.get("weaknesses_reasoning_chain") or []
                                
                                if isinstance(old_strengths, list):
                                    strengths_chain = old_strengths
                                if isinstance(old_weaknesses, list):
                                    weaknesses_chain = old_weaknesses
                            
                            # ========== 3. 一句话总结 ==========
                            summary_text = _generate_summary_text(strengths_chain, weaknesses_chain)
                            st.markdown(summary_text)
                            
                            st.markdown("---")
                            
                            # ========== 4. 两列布局（Desktop）& 单列布局（Mobile） ==========
                            col_left, col_right = st.columns([1, 1])
                            
                            with col_left:
                                # ========== 雷达图（使用Ultra score_dims字段）==========
                                # 优先使用Ultra格式的score_dims
                                score_dims = row.get("score_dims", {})
                                if score_dims and isinstance(score_dims, dict):
                                    scores_dict = {
                                        "技能匹配度": float(score_dims.get("skill_match", 0) or 0),
                                        "经验相关性": float(score_dims.get("experience_match", 0) or 0),
                                        "成长潜力": float(score_dims.get("growth_potential", 0) or 0),
                                        "稳定性": float(score_dims.get("stability", 0) or 0),
                                    }
                                else:
                                    # 兼容旧字段（从维度得分获取）
                                    scores_dict = {
                                        "技能匹配度": float(row.get("技能匹配度", 0) or 0),
                                        "经验相关性": float(row.get("经验相关性", 0) or 0),
                                        "成长潜力": float(row.get("成长潜力", 0) or 0),
                                        "稳定性": float(row.get("稳定性", 0) or 0),
                                    }
                                
                                st.markdown("**📊 评分维度雷达图**")
                                
                                # 获取标准模型（如果有）
                                standard_model = row.get("standard_model", {})
                                if not standard_model or not isinstance(standard_model, dict):
                                    # 尝试从其他字段获取
                                    standard_model = row.get("standard_ability_model", {})
                                
                                # 如果有标准模型，显示说明
                                if standard_model and isinstance(standard_model, dict):
                                    st.caption("📌 红色虚线：岗位标准能力模型 | 蓝色实线：候选人实际能力")
                                
                                # 创建雷达图：使用候选人ID+uuid生成唯一key避免冲突
                                try:
                                    radar_fig = _create_radar_chart(scores_dict, standard_model)
                                    if radar_fig:
                                        # 使用候选人ID（如果有）和uuid生成唯一key
                                        candidate_id = str(row.get("候选人ID", "")) or str(row.get("id", "")) or "unknown"
                                        unique_key = f"radar_{candidate_id}_{uuid.uuid4().hex[:8]}"
                                        st.plotly_chart(radar_fig, use_container_width=True, key=unique_key)
                                except ImportError as e:
                                    # plotly 未安装 - 显示详细错误信息用于调试
                                    import sys
                                    st.error(f"❌ Plotly 导入失败: {str(e)}")
                                    st.info(f"💡 Python 路径: {sys.executable}")
                                    st.info("💡 提示：安装 plotly 可查看雷达图可视化")
                                    st.info(f"💡 请运行: pip install plotly kaleido")
                                    score_table = pd.DataFrame({
                                        "维度": ["技能匹配度", "经验相关性", "成长潜力", "稳定性"],
                                        "得分": [
                                            scores_dict.get("技能匹配度", 0),
                                            scores_dict.get("经验相关性", 0),
                                            scores_dict.get("成长潜力", 0),
                                            scores_dict.get("稳定性", 0),
                                        ]
                                    })
                                    st.dataframe(score_table, use_container_width=True, hide_index=True)
                                except Exception as e:
                                    # 其他错误（创建失败、渲染失败等）
                                    st.warning(f"⚠️ 雷达图显示失败: {str(e)[:150]}")
                                    # 显示文本表格作为替代
                                    score_table = pd.DataFrame({
                                        "维度": ["技能匹配度", "经验相关性", "成长潜力", "稳定性"],
                                        "得分": [
                                            scores_dict.get("技能匹配度", 0),
                                            scores_dict.get("经验相关性", 0),
                                            scores_dict.get("成长潜力", 0),
                                            scores_dict.get("稳定性", 0),
                                        ]
                                    })
                                    st.dataframe(score_table, use_container_width=True, hide_index=True)
                                
                                # ========== 优势总结（从evidence_chains提取）==========
                                with st.expander("✅ **优势总结**", expanded=False):
                                    # 优先使用Ultra格式的strengths_reasoning_chain
                                    if strengths_chain:
                                        for idx, item in enumerate(strengths_chain, 1):
                                            if not isinstance(item, dict):
                                                continue
                                            # Ultra-Format字段
                                            conclusion = item.get('conclusion', item.get('action', '无结论'))
                                            detected_actions = item.get('detected_actions', item.get('action', ''))
                                            resume_evidence = item.get('resume_evidence', item.get('evidence', ''))
                                            ai_reasoning = item.get('ai_reasoning', item.get('reasoning', ''))
                                            
                                            st.markdown(f"**{idx}. {conclusion}**")
                                            if detected_actions:
                                                st.markdown(f"   *动作：* {detected_actions[:80]}")
                                            if resume_evidence:
                                                st.markdown(f"   *证据：* {resume_evidence[:80]}")
                                            if ai_reasoning:
                                                st.markdown(f"   *推理：* {ai_reasoning[:100]}")
                                            if idx < len(strengths_chain):
                                                st.markdown("---")
                                    else:
                                        st.caption("暂无相关记录")
                                
                                # ========== 劣势总结（从weaknesses_reasoning_chain提取）==========
                                with st.expander("⚠️ **劣势总结**", expanded=False):
                                    # 优先使用Ultra格式的weaknesses_reasoning_chain
                                    if weaknesses_chain:
                                        for idx, item in enumerate(weaknesses_chain, 1):
                                            if isinstance(item, dict):
                                                # Ultra-Format字段
                                                conclusion = item.get("conclusion", item.get("action", "劣势项"))
                                                resume_gap = item.get("resume_gap", item.get("evidence", ""))
                                                compare_to_jd = item.get("compare_to_jd", "")
                                                ai_reasoning = item.get("ai_reasoning", item.get("reasoning", ""))
                                                
                                                if conclusion or resume_gap or compare_to_jd or ai_reasoning:
                                                    st.markdown(f"**{idx}. {conclusion}**")
                                                    if resume_gap:
                                                        gap_text = resume_gap if isinstance(resume_gap, str) else ", ".join(resume_gap[:3]) if isinstance(resume_gap, list) else str(resume_gap)
                                                        st.markdown(f"   *缺失项：* {gap_text[:80]}")
                                                    if compare_to_jd:
                                                        st.markdown(f"   *对比JD：* {compare_to_jd[:80]}")
                                                    if ai_reasoning:
                                                        st.markdown(f"   *推理：* {ai_reasoning[:100]}")
                                                    if idx < len(weaknesses_chain):
                                                        st.markdown("---")
                                            else:
                                                # 兼容旧格式
                                                conclusion = item.get('conclusion', '无结论') if isinstance(item, dict) else str(item)
                                                st.markdown(f"**{idx}. {conclusion}**")
                                                if idx < len(weaknesses_chain):
                                                    st.markdown("---")
                                    else:
                                        st.caption("暂无相关记录")
                            
                            with col_right:
                                # ========== 证据链详情（Ultra格式：四维度完整显示）==========
                                evidence_chains_ultra = row.get("evidence_chains", {})
                                evidence_text_ultra = row.get("evidence_text", "")
                                
                                if evidence_chains_ultra and isinstance(evidence_chains_ultra, dict) and len(evidence_chains_ultra) > 0:
                                    # 使用Ultra格式的证据链（四维度）
                                    with st.expander("📋 **证据链详情**", expanded=False):
                                        dimension_order = ["技能匹配度", "经验相关性", "成长潜力", "稳定性"]
                                        for dim in dimension_order:
                                            if dim in evidence_chains_ultra:
                                                dim_evidences = evidence_chains_ultra[dim]
                                                if isinstance(dim_evidences, list) and len(dim_evidences) > 0:
                                                    st.markdown(f"### 【{dim}】")
                                                    for idx, ev in enumerate(dim_evidences, 1):
                                                        if isinstance(ev, dict):
                                                            action = ev.get('action', '暂无')
                                                            evidence = ev.get('evidence', '暂无')
                                                            reasoning = ev.get('reasoning', '暂无')
                                                            
                                                            st.markdown(f"**{idx}. 动作：** {action}")
                                                            if len(evidence) > 80:
                                                                evidence = evidence[:80] + "..."
                                                            st.markdown(f"   **原文证据：** {evidence}")
                                                            if len(reasoning) > 100:
                                                                reasoning = reasoning[:100] + "..."
                                                            st.markdown(f"   **推理：** {reasoning}")
                                                            if idx < len(dim_evidences):
                                                                st.markdown("---")
                                                    if dim != dimension_order[-1]:
                                                        st.markdown("")
                                elif evidence_text_ultra:
                                    # 回退到文本格式
                                    with st.expander("📋 **证据链详情**", expanded=False):
                                        st.markdown(f'<div style="white-space: pre-wrap; line-height: 1.6;">{evidence_text_ultra}</div>', unsafe_allow_html=True)
                                else:
                                    # 回退到旧格式推理链
                                    with st.expander("🔍 **优势推理链详情**", expanded=False):
                                        if strengths_chain:
                                            for idx, item in enumerate(strengths_chain, 1):
                                                if isinstance(item, dict):
                                                    action = item.get("action", item.get("detected_actions", "未提供"))
                                                    evidence = item.get("evidence", item.get("resume_evidence", "未提供"))
                                                    reasoning = item.get("reasoning", item.get("ai_reasoning", "未提供"))
                                                    st.markdown(f"""
                                                    <div class="reasoning-item">
                                                        <strong>{idx}. {action}</strong><br/>
                                                        <small>证据：{evidence[:80]}</small><br/>
                                                        <small>推断：{reasoning[:100]}</small>
                                                    </div>
                                                    """, unsafe_allow_html=True)
                                        else:
                                            st.caption("暂无相关记录")
                                    
                                    with st.expander("🔍 **劣势推理链详情**", expanded=False):
                                        if weaknesses_chain:
                                            for idx, item in enumerate(weaknesses_chain, 1):
                                                if isinstance(item, dict):
                                                    action = item.get("action", item.get("resume_gap", "未提供"))
                                                    evidence = item.get("evidence", item.get("compare_to_jd", "未提供"))
                                                    reasoning = item.get("reasoning", item.get("ai_reasoning", "未提供"))
                                                    st.markdown(f"""
                                                    <div class="reasoning-item">
                                                        <strong>{idx}. {action}</strong><br/>
                                                        <small>证据：{evidence[:80]}</small><br/>
                                                        <small>风险：{reasoning[:100]}</small>
                                                    </div>
                                                    """, unsafe_allow_html=True)
                                        else:
                                            st.caption("暂无相关记录")

                    # ✅ 一键修复版：AI 匹配完成后自动保存 & 跳转

                    # 判断AI匹配结果是否为空
                    if "result_df" in locals() and not result_df.empty:
                        # 保存评分结果到session_state，供下一步“去重&排序”使用
                        st.session_state["score_df"] = result_df
                        st.session_state["scored"] = result_df

                        # 显示成功提示
                        st.success("AI 匹配分析完成 ✅")
                        st.info("系统已自动保存评分结果，请点击顶部导航栏『3 去重 & 排序』查看 Top-N 候选人。")

                        # 自动导出CSV文件到项目data目录
                        import os
                        output_path = os.path.join("data", "ai_match_results.csv")
                        try:
                            export_df.to_csv(output_path, index=False, encoding="utf-8-sig")
                            st.write(f"✅ 已自动保存匹配结果至 `{output_path}`")
                        except Exception as e:
                            st.warning(f"⚠️ 保存CSV失败: {e}")

                        # （可选）提供下载按钮
                        st.download_button(
                            label="⬇️ 下载 AI 匹配结果（CSV）",
                            data=export_df.to_csv(index=False).encode("utf-8-sig"),
                            file_name="ai_match_results.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning("⚠️ 暂无匹配结果，请先完成AI匹配评分后再尝试。")
    else:
        st.info("请上传一批简历文件开始分析。")

with tab3:
    st.subheader("去重 & 排序（展示 Top-N）")
    topn = st.slider("Top-N", 5, 50, 10)
    st.session_state["topn_limit"] = topn
    score_source = None
    if "score_df" in st.session_state:
        score_source = st.session_state["score_df"]
    elif "scored" in st.session_state:
        score_source = st.session_state["scored"]

    if score_source is not None:
        # 去重排序
        deduped = pipe.dedup_and_rank(score_source)
        st.session_state["shortlist"] = deduped.head(topn)
        shortlist_ids: list[str] = []
        if "candidate_id" in st.session_state["shortlist"].columns:
            shortlist_ids = (
                st.session_state["shortlist"]["candidate_id"].astype(str).tolist()
            )
        elif "序号" in st.session_state["shortlist"].columns:
            shortlist_ids = (
                st.session_state["shortlist"]["序号"].astype(str).tolist()
            )
        st.session_state["topn_ids"] = shortlist_ids
        
        # 使用与tab2完全一致的字段显示顺序和逻辑
        display_columns = [
            "candidate_id",
            "name",
            "file",
            "总分",
            "技能匹配度",
            "经验相关性",
            "成长潜力",
            "稳定性",
            "short_eval",
            "highlights",
            "resume_mini",
            "证据",
        ]
        
        # 只选择存在的列，保持顺序（与tab2逻辑完全一致）
        existing_display = [col for col in display_columns if col in deduped.columns]
        if existing_display:
            # 创建显示用的DataFrame副本，确保数据不被修改
            deduped_display = deduped.head(topn)[existing_display].copy()
            
            # 对resume_mini进行长度限制（与tab2完全一致）
            if "resume_mini" in deduped_display.columns:
                deduped_display["resume_mini"] = deduped_display["resume_mini"].apply(
                    lambda x: (x[:80] + "…") if isinstance(x, str) and len(x) > 80 else x
                )
            
            # 汉化显示（与tab2完全一致）
            deduped_display = translate_dataframe_columns(deduped_display)
            st.dataframe(
                deduped_display,
                use_container_width=True,
                hide_index=True,
            )
        else:
            # 如果没有匹配的列，显示原始数据
            deduped_display = translate_dataframe_columns(deduped.head(topn))
            st.dataframe(deduped_display, use_container_width=True, hide_index=True)
    else:
        st.warning("请先完成评分")

with tab4:
    st.subheader("🤖 一键邀约 + 自动排期")
    st.markdown("让AI帮你生成个性化邀约邮件（含候选亮点 + 日历附件）")

    # 优先使用去重&排序后的shortlist，如果没有则使用原始score_df
    shortlist = st.session_state.get("shortlist")
    score_df = st.session_state.get("score_df")
    
    if shortlist is not None and not shortlist.empty:
        # 使用去重&排序后的结果
        df = shortlist.copy()
        st.info(f"✅ 已使用「去重&排序」步骤筛选后的 Top-{len(df)} 名候选人")
    elif score_df is not None and not score_df.empty:
        # 如果没有shortlist，使用原始score_df（需要先排序）
        df = score_df.copy()
        # 按总分降序排序
        if "总分" in df.columns:
            df = df.sort_values(by="总分", ascending=False, ignore_index=True)
        elif "score_total" in df.columns:
            df = df.sort_values(by="score_total", ascending=False, ignore_index=True)
        st.warning("⚠️ 建议先在「去重&排序」步骤中筛选候选人，当前使用原始评分结果（已按总分排序）")
    else:
        st.warning("请先完成AI匹配评分。")
        df = None
    
    if df is not None and not df.empty:
        max_candidates = len(df)
        default_top = min(5, max_candidates)
        top_n = st.number_input(
            "选择要邀约的候选人数（Top-N）",
            min_value=1,
            max_value=max_candidates,
            value=default_top,
            step=1,
        )
        top_n = int(top_n)
        selected_candidates = df.head(top_n)

        score_col = "总分" if "总分" in df.columns else "score_total" if "score_total" in df.columns else None
        display_cols = [
            col
            for col in [
                "name",
                "file",
                "email",
                "phone",
                score_col,
                "技能匹配度",
                "经验相关性",
                "成长潜力",
                "稳定性",
                "short_eval",
                "highlights",
                "resume_mini",
            ]
            if col and col in df.columns
        ]
        if not display_cols:
            display_cols = df.columns.tolist()

        st.write(f"已选择 {top_n} 位候选人：")
        st.dataframe(selected_candidates[display_cols], use_container_width=True)

        # 时区选择（全局设置）
        timezone = st.selectbox("🌍 时区", ["Asia/Shanghai", "Asia/Beijing", "UTC"], index=0)
        
        # 为每位候选人单独设置面试时间
        st.markdown("### 📅 为每位候选人设置面试时间")
        st.info("💡 每位候选人可以设置不同的面试时间，避免群面冲突")
        
        candidate_interview_times = {}
        candidate_interview_locations = {}
        
        # 默认面试时间和地点
        default_date = datetime.now().date() + timedelta(days=1)
        default_time = datetime.strptime("14:00", "%H:%M").time()
        default_location = "公司会议室（具体地址待确认）"
        
        for idx, (_, row) in enumerate(selected_candidates.iterrows()):
            row_dict = row.to_dict()
            candidate_name = row_dict.get("name") or row_dict.get("file") or f"候选人{idx+1}"
            
            with st.expander(f"📅 {candidate_name} 的面试安排", expanded=(idx == 0)):
                col_date, col_time = st.columns(2)
                with col_date:
                    # 从session_state获取之前设置的时间，如果没有则使用默认值
                    date_key = f"interview_date_{idx}"
                    prev_date = st.session_state.get(date_key, default_date)
                    interview_date = st.date_input(
                        "面试日期",
                        value=prev_date,
                        key=date_key,
                        label_visibility="visible"
                    )
                with col_time:
                    time_key = f"interview_time_{idx}"
                    prev_time = st.session_state.get(time_key, default_time)
                    interview_hour = st.time_input(
                        "面试时间",
                        value=prev_time,
                        key=time_key,
                        label_visibility="visible"
                    )
                
                # 格式化面试时间字符串
                interview_datetime = datetime.combine(interview_date, interview_hour)
                interview_time_str = f"{interview_datetime.strftime('%Y-%m-%d %H:%M')}, {timezone}"
                candidate_interview_times[idx] = interview_time_str
                
                # 面试地点（可以为每个候选人单独设置）
                location_key = f"interview_location_{idx}"
                prev_location = st.session_state.get(location_key, default_location if idx == 0 else "")
                interview_location = st.text_input(
                    "📍 面试地点",
                    value=prev_location,
                    key=location_key,
                    help="可为每位候选人设置不同的面试地点",
                    label_visibility="visible"
                )
                candidate_interview_locations[idx] = interview_location or default_location
        
        # 全局面试地点和时间（如果所有候选人使用相同地点和时间，可以在这里设置）
        st.markdown("---")
        st.markdown("### 🌐 统一面试设置（可选）")
        st.info("💡 如果所有候选人使用相同的时间和地点，可以在这里统一设置，将覆盖上述单独设置")
        
        # 是否启用统一面试时间
        use_unified_time = st.checkbox("✅ 使用统一面试时间", value=False, help="勾选后，所有候选人将使用相同的面试时间")
        
        # 统一面试时间（仅在启用时显示）
        unified_interview_time_str = None
        if use_unified_time:
            col_unified_date, col_unified_time = st.columns(2)
            with col_unified_date:
                unified_date_key = "unified_interview_date"
                prev_unified_date = st.session_state.get(unified_date_key, default_date)
                unified_interview_date = st.date_input(
                    "📅 统一面试日期",
                    value=prev_unified_date,
                    key=unified_date_key,
                    help="将应用于所有候选人",
                    label_visibility="visible"
                )
            with col_unified_time:
                unified_time_key = "unified_interview_time"
                prev_unified_time = st.session_state.get(unified_time_key, default_time)
                unified_interview_hour = st.time_input(
                    "⏰ 统一面试时间",
                    value=prev_unified_time,
                    key=unified_time_key,
                    help="将应用于所有候选人",
                    label_visibility="visible"
                )
            
            # 格式化统一面试时间字符串
            unified_interview_datetime = datetime.combine(unified_interview_date, unified_interview_hour)
            unified_interview_time_str = f"{unified_interview_datetime.strftime('%Y-%m-%d %H:%M')}, {timezone}"
        
        # 统一面试地点
        interview_location = st.text_input("📍 统一面试地点（可选，如为空则使用上述单独设置的地点）", value="", help="如果所有候选人使用相同地点，可以在这里统一设置")
        
        organizer_email = st.text_input("📧 面试组织者邮箱", value=os.getenv("SMTP_USER", "hr@company.com"))
        
        # 企业微信配置（可选）
        with st.expander("📱 企业微信配置（可选）"):
            organizer_name = st.text_input("组织者姓名", "HR", help="用于企业微信消息中的联系人显示", key="organizer_name")
            organizer_wechat = st.text_input("组织者企业微信ID", "", help="可选，用于生成企业微信添加链接", key="organizer_wechat")
            meeting_link = st.text_input("会议链接（可选）", "", help="如：腾讯会议链接、Zoom链接等", key="meeting_link")

        # 检查是否已有生成的邮件
        existing_invites = st.session_state.get("invite_results", [])
        show_existing = False
        if existing_invites and len(existing_invites) > 0:
            st.info(f"💡 检测到已有 {len(existing_invites)} 封已生成的邮件，您可以继续编辑或直接发送。如需重新生成，请点击下方按钮。")
            show_existing = True

        if st.button("🚀 一键生成邀约邮件 + ICS"):
            # 获取企业微信配置（如果未设置，使用默认值）
            organizer_name = st.session_state.get("organizer_name", "HR")
            organizer_wechat = st.session_state.get("organizer_wechat", "")
            meeting_link = st.session_state.get("meeting_link", "")
            st.info("AI 正在生成个性化邀约内容，请稍候...")

            invite_results = []
            invites_dir = "reports/invites"
            os.makedirs(invites_dir, exist_ok=True)

            job_title = st.session_state.get("job_name") or "目标岗位"

            # 生成默认面试时间作为fallback
            default_interview_datetime = datetime.combine(default_date, default_time)
            default_interview_time_str = f"{default_interview_datetime.strftime('%Y-%m-%d %H:%M')}, {timezone}"

            for idx, (_, row) in enumerate(selected_candidates.iterrows()):
                row_dict = row.to_dict()
                # 优先使用name字段（姓名），如果没有则使用file字段（文件名），最后使用默认值
                candidate_name_raw = row_dict.get("name") or row_dict.get("file") or "匿名候选人"
                # 添加先生/女士称呼
                candidate_name = add_name_title(candidate_name_raw, row_dict)
                candidate_email = row_dict.get("email", "")
                candidate_score = row_dict.get("总分") or row_dict.get("score_total") or row_dict.get("score", "未知")

                # 获取该候选人的面试时间和地点
                # 如果启用了统一时间，优先使用统一时间；否则使用候选人单独设置的时间
                if use_unified_time and unified_interview_time_str:
                    candidate_interview_time = unified_interview_time_str
                else:
                    candidate_interview_time = candidate_interview_times.get(idx, default_interview_time_str)
                
                # 如果设置了统一地点，优先使用统一地点；否则使用候选人单独设置的地点
                if interview_location and interview_location.strip():
                    candidate_interview_location = interview_location
                else:
                    candidate_interview_location = candidate_interview_locations.get(idx, default_location)

                try:
                    candidate_highlight = generate_ai_summary(row_dict)
                except Exception as e:
                    candidate_highlight = f"AI 总结失败：{e}"

                try:
                    # 生成ICS文件描述
                    ics_description = f"请准时参加面试。如需调整时间请及时联系HR。\n岗位：{job_title}\n面试地点：{candidate_interview_location or '待确认'}"
                    ics_path = create_ics_file(
                        title=f"{job_title}岗位面试",
                        start_time=candidate_interview_time,
                        organizer=organizer_email,
                        attendee=candidate_email or "candidate@example.com",
                        location=candidate_interview_location or "",
                        description=ics_description,
                    )
                except Exception as e:
                    st.warning(f"生成 {candidate_name} 的日历文件失败：{e}")
                    ics_path = ""

                try:
                    email_body = generate_ai_email(
                        name=candidate_name,
                        highlights=candidate_highlight,
                        position=job_title,
                        score=candidate_score,
                        ics_path=ics_path or "(附件生成失败)",
                    )
                    # 在邮件正文中添加面试地点信息
                    if candidate_interview_location and candidate_interview_location.strip():
                        location_note = f"\n\n📍 面试地点：{candidate_interview_location}"
                        email_body = email_body + location_note
                except Exception as e:
                    email_body = f"AI 邮件生成失败：{e}"

                # 生成邮件主题：关于 {姓名} 应聘 {岗位} 的面试安排通知
                email_subject = f"关于 {candidate_name} 应聘 {job_title} 的面试安排通知"

                invite_results.append(
                    {
                        "candidate_id": str(row_dict.get("candidate_id") or row_dict.get("序号") or row_dict.get("id") or ""),
                        "file": row_dict.get("file"),
                        "name": candidate_name,
                        "email": candidate_email,
                        "ics": ics_path,
                        "body": email_body,
                        "subject": email_subject,
                        "highlights": candidate_highlight,
                        "score": candidate_score,
                        "position": job_title,
                        "interview_time": candidate_interview_time,
                        "interview_location": candidate_interview_location,
                        "email_sent": False,
                        "email_sent_at": "",
                        "email_status": "",
                        "wechat_sent": False,
                    }
                )

            json_payload = json.dumps(invite_results, ensure_ascii=False, indent=2)
            json_path = os.path.join(invites_dir, f"invite_batch_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
            with open(json_path, "w", encoding="utf-8") as fp:
                fp.write(json_payload)

            st.success("✅ AI 个性化邀约生成完成！")
            
            # 保存到session_state，供后续编辑和发送使用
            st.session_state["invite_results"] = invite_results
            st.session_state["job_title"] = job_title
            # 保存每个候选人的面试时间配置（用于后续编辑）
            st.session_state["candidate_interview_times"] = candidate_interview_times
            st.session_state["candidate_interview_locations"] = candidate_interview_locations
        
        # 显示邮件预览和编辑功能（无论是新生成还是已有邮件）
        invite_results = st.session_state.get("invite_results", [])
        if invite_results and len(invite_results) > 0:
            job_title = st.session_state.get("job_title", "目标岗位")
            # interview_time 和 interview_location 在已有邮件时从session_state获取，新生成时使用上面的值
            default_interview_time = f"{datetime.combine(datetime.now().date() + timedelta(days=1), datetime.strptime('14:00', '%H:%M').time()).strftime('%Y-%m-%d %H:%M')}, {timezone}"
            interview_time = st.session_state.get("interview_time", default_interview_time)
            interview_location = st.session_state.get("interview_location", "公司会议室（具体地址待确认）")
            
            # 邮件预览和编辑功能
            st.markdown("### 📧 邮件预览与编辑")
            st.info("💡 在发送前，您可以预览和编辑每封邮件的内容")
            
            for idx, invite in enumerate(invite_results):
                with st.expander(f"📧 {invite.get('name', f'候选人{idx+1}')} - {invite.get('email', '')}", expanded=(idx == 0)):
                    col_preview1, col_preview2 = st.columns([2, 1])
                    
                    with col_preview1:
                        st.markdown("**邮件主题：**")
                        subject_key = f"subject_{idx}"
                        # 智能识别岗位和姓名：优先使用invite中的position和name，如果没有则使用job_title和默认值
                        position_for_subject = invite.get("position", job_title)
                        candidate_name_for_subject = invite.get("name", "您")
                        email_subject = st.text_input(
                            "主题",
                            value=invite.get("subject", f"关于 {candidate_name_for_subject} 应聘 {position_for_subject} 的面试安排通知"),
                            key=subject_key,
                            label_visibility="collapsed"
                        )
                        
                        st.markdown("**邮件正文：**")
                        body_key = f"body_{idx}"
                        edited_body = st.text_area(
                            "正文",
                            value=invite.get("body", ""),
                            height=300,
                            key=body_key,
                            label_visibility="collapsed"
                        )
                        
                        # 更新invite_results中的内容
                        invite_results[idx]["body"] = edited_body
                        invite_results[idx]["subject"] = email_subject
                    
                    with col_preview2:
                        st.markdown("**邮件信息：**")
                        st.write(f"📧 **收件人：** {invite.get('email', '未提供')}")
                        st.write(f"📅 **面试时间：** {invite.get('interview_time', '未设置')}")
                        st.write(f"📍 **面试地点：** {invite.get('interview_location', '未设置')}")
                        st.write(f"💼 **岗位：** {invite.get('position', '未设置')}")
                        st.write(f"⭐ **评分：** {invite.get('score', '未知')}")
                        
                        if invite.get("ics"):
                            st.success("✅ 日历附件已生成")
                        else:
                            st.warning("⚠️ 日历附件未生成")
                        
                        st.markdown("**亮点摘要：**")
                        st.caption(invite.get("highlights", "无")[:200])
            
            # 更新session_state中的编辑后内容
            st.session_state["invite_results"] = invite_results
            
            # 保存JSON文件
            json_payload = json.dumps(invite_results, ensure_ascii=False, indent=2)
            json_path = os.path.join("reports/invites", f"invite_batch_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
            os.makedirs("reports/invites", exist_ok=True)
            with open(json_path, "w", encoding="utf-8") as fp:
                fp.write(json_payload)
            
            # 企业微信集成
            st.markdown("### 📱 企业微信邀约")
            try:
                from backend.services.wechat_integration import create_wechat_invite_template
                
                wechat_results = []
                for invite in invite_results:
                    wechat_data = create_wechat_invite_template({
                        "name": invite.get("name", ""),
                        "email": invite.get("email", ""),
                        "position": invite.get("position", job_title),
                        "interview_time": invite.get("interview_time", interview_time),
                        "highlights": invite.get("highlights", ""),
                        "meeting_link": meeting_link,
                        "organizer_name": organizer_name,
                        "organizer_wechat": organizer_wechat,
                    })
                    wechat_results.append(wechat_data)
                
                # 显示企业微信消息（可复制）
                for idx, (invite, wechat_data) in enumerate(zip(invite_results, wechat_results)):
                    with st.expander(f"📱 {invite.get('name', f'候选人{idx+1}')} - 企业微信消息"):
                        st.text_area(
                            "企业微信消息内容（点击复制）",
                            value=wechat_data.get("wechat_message", ""),
                            height=200,
                            key=f"wechat_msg_{idx}",
                            help="复制此内容到企业微信发送给候选人"
                        )
                        if wechat_data.get("meeting_link"):
                            st.write(f"🔗 会议链接：{wechat_data.get('meeting_link')}")
                        if wechat_data.get("wechat_link"):
                            st.write(f"📱 {wechat_data.get('wechat_link')}")
            except Exception as e:
                st.info(f"💡 企业微信功能：{str(e)}")
            
            # 邮件导入企业邮箱
            st.markdown("### 📧 邮件导入企业邮箱")
            col1, col2 = st.columns(2)
            
            with col1:
                try:
                    from backend.services.email_integration import generate_email_import_file, generate_outlook_import_csv
                    
                    if st.button("📥 生成邮件导入文件（.eml）"):
                        with st.spinner("正在生成邮件导入文件..."):
                            import_path = generate_email_import_file(invite_results)
                            if import_path:
                                st.success(f"✅ 邮件文件已生成：`{import_path}`")
                                st.info("💡 使用方法：\n1. Outlook：文件 -> 打开 -> 其他文件 -> 选择 .eml 文件\n2. 企业邮箱：设置 -> 导入邮件 -> 选择 .eml 文件")
                            else:
                                st.warning("⚠️ 生成失败，请检查数据")
                except Exception as e:
                    st.warning(f"邮件导入功能：{str(e)}")
            
            with col2:
                try:
                    if st.button("📋 生成Outlook导入CSV"):
                        with st.spinner("正在生成CSV文件..."):
                            csv_path = generate_outlook_import_csv(invite_results)
                            if csv_path:
                                with open(csv_path, 'rb') as f:
                                    st.download_button(
                                        "⬇️ 下载Outlook导入CSV",
                                        data=f.read(),
                                        file_name=os.path.basename(csv_path),
                                        mime="text/csv"
                                    )
                                st.success(f"✅ CSV文件已生成：`{csv_path}`")
                except Exception as e:
                    st.warning(f"CSV生成功能：{str(e)}")
            
            # SMTP邮件发送（可选）
            with st.expander("📮 通过SMTP直接发送邮件（需要配置）", expanded=True):
                st.info("💡 需要在 .env 文件中配置以下参数：\n- SMTP_SERVER（如：smtp.exmail.qq.com）\n- SMTP_PORT（默认587）\n- SMTP_USER（邮箱地址）\n- SMTP_PASSWORD（邮箱密码或授权码）")
                
                smtp_server = st.text_input("SMTP服务器", os.getenv("SMTP_SERVER", ""), help="如：smtp.exmail.qq.com")
                smtp_port = st.number_input("SMTP端口", value=int(os.getenv("SMTP_PORT", "587")), min_value=1, max_value=65535)
                smtp_user = st.text_input("SMTP用户名（邮箱）", os.getenv("SMTP_USER", ""))
                smtp_password = st.text_input("SMTP密码/授权码", type="password", value=os.getenv("SMTP_PASSWORD", ""))
                
                # 发送前确认
                if st.button("📤 批量发送邮件", type="primary"):
                    if not smtp_server or not smtp_user or not smtp_password:
                        st.error("❌ 请先配置SMTP参数")
                    elif not invite_results:
                        st.error("❌ 没有可发送的邮件，请先生成邀约邮件")
                    else:
                        try:
                            from backend.services.email_integration import send_email_via_smtp
                            
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            success_count = 0
                            fail_count = 0
                            send_results = []
                            
                            total = len(invite_results)
                            for idx, invite in enumerate(invite_results):
                                candidate_name = invite.get("name", f"候选人{idx+1}")
                                candidate_email = invite.get("email", "")
                                
                                # 更新进度
                                progress = (idx + 1) / total
                                progress_bar.progress(progress)
                                status_text.text(f"正在发送 ({idx + 1}/{total}): {candidate_name} ({candidate_email})")
                                
                                # 获取编辑后的邮件内容，智能识别岗位和姓名
                                position_for_subject = invite.get("position", job_title)
                                candidate_name_for_subject = invite.get("name", "您")
                                email_subject = invite.get("subject", f"关于 {candidate_name_for_subject} 应聘 {position_for_subject} 的面试安排通知")
                                email_body = invite.get("body", "")
                                
                                if not candidate_email or not candidate_email.strip():
                                    result = {
                                        "success": False,
                                        "message": "收件人邮箱为空"
                                    }
                                else:
                                    result = send_email_via_smtp(
                                        to_email=candidate_email,
                                        subject=email_subject,
                                        body=email_body,
                                        ics_path=invite.get("ics", ""),
                                        smtp_server=smtp_server,
                                        smtp_port=smtp_port,
                                        smtp_user=smtp_user,
                                        smtp_password=smtp_password,
                                        from_email=smtp_user
                                    )
                                
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                invite["email_sent"] = result.get("success", False)
                                invite["email_sent_at"] = timestamp if result.get("success") else ""
                                invite["email_status"] = result.get("message", "")
                                send_results.append({
                                    "name": candidate_name,
                                    "email": candidate_email,
                                    "success": result.get("success", False),
                                    "message": result.get("message", "")
                                })
                                
                                if result.get("success"):
                                    success_count += 1
                                else:
                                    fail_count += 1
                            
                            progress_bar.empty()
                            status_text.empty()
                            
                            # 显示发送结果
                            st.markdown("### 📊 发送结果")
                            if success_count > 0:
                                st.success(f"✅ 成功发送 {success_count} 封邮件")
                            if fail_count > 0:
                                st.error(f"❌ 发送失败 {fail_count} 封邮件")
                            
                            # 显示详细结果
                            with st.expander("📋 详细发送结果", expanded=(fail_count > 0)):
                                for result in send_results:
                                    if result["success"]:
                                        st.success(f"✅ {result['name']} ({result['email']}) - 发送成功")
                                    else:
                                        st.error(f"❌ {result['name']} ({result['email']}) - {result['message']}")
                            
                            # 保存发送结果
                            st.session_state["send_results"] = send_results
                            st.session_state["invite_results"] = invite_results
                            
                        except Exception as e:
                            st.error(f"❌ 发送失败：{str(e)}")
                            import traceback
                            st.code(traceback.format_exc())
            
            st.download_button(
                "📥 下载邀约结果（JSON）",
                data=json_payload,
                file_name="ai_invites.json",
                mime="application/json",
            )

            # 保存待面试清单（带错误处理）
            pending_path = "reports/pending_interviews.csv"
            try:
                # 确保目录存在
                import os
                os.makedirs("reports", exist_ok=True)
                
                # 尝试写入文件
                pd.DataFrame(invite_results).to_csv(pending_path, index=False, encoding="utf-8-sig")
                st.write(f"📋 已自动更新待面试清单：`{pending_path}`")
            except PermissionError:
                # 如果文件被占用（如 Excel 打开），使用带时间戳的文件名
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                pending_path_alt = f"reports/pending_interviews_{timestamp}.csv"
                try:
                    pd.DataFrame(invite_results).to_csv(pending_path_alt, index=False, encoding="utf-8-sig")
                    st.warning(f"⚠️ 原文件被占用，已保存到：`{pending_path_alt}`")
                    st.info("💡 提示：请关闭可能正在打开 `pending_interviews.csv` 的程序（如 Excel）")
                except Exception as e:
                    st.warning(f"⚠️ 保存待面试清单失败：{str(e)}")
            except Exception as e:
                st.warning(f"⚠️ 保存待面试清单失败：{str(e)}")

            st.json(invite_results, expanded=False)

with tab5:
    st.subheader("面试包 & 导出报表")
    if st.button("导出本轮报表"):
        score_df = st.session_state.get("score_df", None)
        scored_df = st.session_state.get("scored", None)

        if score_df is not None and not score_df.empty:
            score_source = score_df
        elif scored_df is not None and not scored_df.empty:
            score_source = scored_df
        else:
            st.warning("未找到可导出的评分数据，请先完成 AI 匹配评分。")
            st.stop()

        job_meta = st.session_state.get("job_meta", {})
        shortlist = st.session_state.get("shortlist")
        topn_ids = st.session_state.get("topn_ids", []) or []
        if (not topn_ids) and shortlist is not None and not shortlist.empty:
            if "candidate_id" in shortlist.columns:
                topn_ids = shortlist["candidate_id"].astype(str).tolist()
            elif "序号" in shortlist.columns:
                topn_ids = shortlist["序号"].astype(str).tolist()
        invite_results = st.session_state.get("invite_results", [])
        communication_meta = _build_invite_lookup(invite_results)
        round_meta = {
            "topn_cutoff": len(topn_ids) or st.session_state.get("topn_limit"),
            "topn_ids": topn_ids,
        }
        path = export_round_report(
            score_source,
            job_meta=job_meta,
            round_meta=round_meta,
            communication_meta=communication_meta,
        )
        st.success("已导出：" + path)

