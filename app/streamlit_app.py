import json
import os
import re
import time

import pandas as pd
import streamlit as st
from datetime import datetime
from pathlib import Path
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
from backend.services.ai_core import generate_ai_summary, generate_ai_email
from backend.services.calendar_utils import create_ics_file
# from backend.services.excel_exporter import generate_competency_excel, export_ability_sheet_to_file  # 函数不存在，已注释

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
    tags = []
    raw = row_dict.get("highlights")
    if isinstance(raw, str):
        tags = [seg.strip() for seg in re.split(r"[｜|，,、；\s]+", raw) if seg.strip()]
    elif isinstance(raw, list):
        tags = [str(seg).strip() for seg in raw if str(seg).strip()]

    if len(tags) < 2:
        strengths_text = row_dict.get("short_eval", "")
        if strengths_text:
            candidates = [seg.strip(" ；;") for seg in re.split(r"[｜|，,、；\s]+", strengths_text) if seg.strip()]
            for item in candidates:
                if len(item) <= 8:
                    tags.append(item)
                if len(tags) >= 3:
                    break

    tags = [tag for tag in tags if tag][:3]
    if len(tags) == 1:
        tags.append("综合能力")
    return "｜".join(tags) if tags else "未提供"


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
    summary = row_dict.get("resume_mini") or row_dict.get("short_eval") or "未提供相关信息"
    return _clean_single_line(summary, default="未提供相关信息", limit=130)


def _format_evidence_field(row_dict):
    reasoning = _safe_load_json(row_dict.get("reasoning_chain"))
    short_eval_struct = _safe_load_json(row_dict.get("short_eval_struct"))

    def _format_strengths():
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

    match_level = _clean_single_line(short_eval_struct.get("match_level"), "无法评估", 4)
    match_reason = _clean_single_line(short_eval_struct.get("match_reason"), "未提供匹配原因", 60)
    match_text = f"{match_level}：{match_reason}"

    evidence_text = f"【优势】{_format_strengths()}【劣势】{_format_weaknesses()}【匹配度】{match_text}"
    return _clean_single_line(evidence_text, default="未提供")


def _build_export_dataframe(result_df, job_title):
    rows = []
    position_name = _clean_single_line(job_title, default="未提供")
    for _, row in result_df.iterrows():
        row_dict = row.to_dict()
        candidate_id = row_dict.get("candidate_id")

        try:
            candidate_id = int(candidate_id)
        except Exception:
            candidate_id = 0

        export_row = {
            "候选人ID": candidate_id,
            "姓名": _clean_single_line(row_dict.get("name"), "未提供"),
            "文件名": _clean_single_line(row_dict.get("file"), "未提供"),
            "岗位": position_name,
            "邮箱": _clean_single_line(row_dict.get("email"), "未提供"),
            "手机号": _clean_single_line(row_dict.get("phone"), "未提供"),
            "总分": int(round(float(row_dict.get("总分", 0)))),
            "亮点": _format_highlights_for_export(row_dict),
            "简历摘要": _format_resume_summary(row_dict),
            "证据": _format_evidence_field(row_dict),
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
                    with st.spinner("AI 正在智能分析匹配度，请稍候…"):
                        scored_df = ai_match_resumes_df(jd_text, resumes_df, job_title)
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
                    
                    result_df = scored_df
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
                    for _, row in result_df.iterrows():
                        score_label = row.get("总分")
                        title = f"{row.get('name','匿名候选人')}｜总分 {score_label if score_label is not None else '—'}"
                        with st.expander(title):
                            raw_highlights = row.get("highlights", "")
                            if isinstance(raw_highlights, str):
                                highlights_raw = [tag.strip() for tag in re.split(r"[｜|，,、\s]+", raw_highlights) if tag.strip()]
                            elif isinstance(raw_highlights, list):
                                highlights_raw = raw_highlights
                            else:
                                highlights_raw = []
                            if highlights_raw:
                                st.markdown(
                                    "**亮点标签**：" + " ".join(f"`{tag}`" for tag in highlights_raw if tag)
                                )
                            else:
                                st.markdown("**亮点标签**：暂无")

                            resume_mini = row.get("resume_mini", "")
                            st.markdown("**短版简历**")
                            st.write(resume_mini if resume_mini else "暂无短版简历")

                            st.markdown("**AI 推理链**")
                            reasoning_raw = row.get("reasoning_chain") or {}
                            try:
                                reasoning_obj = (
                                    json.loads(reasoning_raw)
                                    if isinstance(reasoning_raw, str)
                                    else reasoning_raw
                                )
                            except Exception:
                                reasoning_obj = {}
                            def render_chain(title: str, chain: list, fields: list):
                                st.markdown(f"##### {title}")
                                if not chain:
                                    st.caption("暂无相关记录")
                                    return
                                for idx, item in enumerate(chain, 1):
                                    if not isinstance(item, dict):
                                        continue
                                    st.markdown(f"**{idx}. {item.get('conclusion', '无结论')}**")
                                    for label, key in fields:
                                        value = str(item.get(key, "")).strip()
                                        if value:
                                            st.markdown(f"- {label}：{value}")
                                    st.markdown("---")
                            strengths_chain = reasoning_obj.get("strengths_reasoning_chain") or []
                            weaknesses_chain = reasoning_obj.get("weaknesses_reasoning_chain") or []
                            render_chain(
                                "优势推理链",
                                strengths_chain,
                                [
                                    ("detected_actions", "detected_actions"),
                                    ("resume_evidence", "resume_evidence"),
                                    ("ai_reasoning", "ai_reasoning"),
                                ],
                            )
                            render_chain(
                                "劣势推理链",
                                weaknesses_chain,
                                [
                                    ("resume_gap", "resume_gap"),
                                    ("compare_to_jd", "compare_to_jd"),
                                    ("ai_reasoning", "ai_reasoning"),
                                ],
                            )

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
    score_source = None
    if "score_df" in st.session_state:
        score_source = st.session_state["score_df"]
    elif "scored" in st.session_state:
        score_source = st.session_state["scored"]

    if score_source is not None:
        deduped = pipe.dedup_and_rank(score_source)
        st.session_state["shortlist"] = deduped.head(topn)
        # 汉化显示
        deduped_display = translate_dataframe_columns(deduped.head(topn))
        st.dataframe(deduped_display, use_container_width=True)
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

        interview_time = st.text_input("🕒 面试时间（例：2025-11-15 14:00, Asia/Shanghai）", "2025-11-15 14:00, Asia/Shanghai")
        organizer_email = st.text_input("📧 面试组织者邮箱", "hr@company.com")
        
        # 企业微信配置（可选）
        with st.expander("📱 企业微信配置（可选）"):
            organizer_name = st.text_input("组织者姓名", "HR", help="用于企业微信消息中的联系人显示", key="organizer_name")
            organizer_wechat = st.text_input("组织者企业微信ID", "", help="可选，用于生成企业微信添加链接", key="organizer_wechat")
            meeting_link = st.text_input("会议链接（可选）", "", help="如：腾讯会议链接、Zoom链接等", key="meeting_link")

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

            for _, row in selected_candidates.iterrows():
                row_dict = row.to_dict()
                candidate_name = row_dict.get("file") or row_dict.get("name") or "匿名候选人"
                candidate_email = row_dict.get("email", "")
                candidate_score = row_dict.get("总分") or row_dict.get("score_total") or row_dict.get("score", "未知")

                try:
                    candidate_highlight = generate_ai_summary(row_dict)
                except Exception as e:
                    candidate_highlight = f"AI 总结失败：{e}"

                try:
                    ics_path = create_ics_file(
                        title=f"面试邀约 - {candidate_name}",
                        start_time=interview_time,
                        organizer=organizer_email,
                        attendee=candidate_email or "candidate@example.com",
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
                except Exception as e:
                    email_body = f"AI 邮件生成失败：{e}"

                invite_results.append(
                    {
                        "name": candidate_name,
                        "email": candidate_email,
                        "ics": ics_path,
                        "body": email_body,
                        "highlights": candidate_highlight,
                        "score": candidate_score,
                        "position": job_title,
                        "interview_time": interview_time,
                    }
                )

            json_payload = json.dumps(invite_results, ensure_ascii=False, indent=2)
            json_path = os.path.join(invites_dir, f"invite_batch_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
            with open(json_path, "w", encoding="utf-8") as fp:
                fp.write(json_payload)

            st.success("✅ AI 个性化邀约生成完成！")
            
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
            with st.expander("📮 通过SMTP直接发送邮件（需要配置）"):
                st.info("💡 需要在 .env 文件中配置以下参数：\n- SMTP_SERVER（如：smtp.exmail.qq.com）\n- SMTP_PORT（默认587）\n- SMTP_USER（邮箱地址）\n- SMTP_PASSWORD（邮箱密码或授权码）")
                
                smtp_server = st.text_input("SMTP服务器", os.getenv("SMTP_SERVER", ""), help="如：smtp.exmail.qq.com")
                smtp_port = st.number_input("SMTP端口", value=int(os.getenv("SMTP_PORT", "587")), min_value=1, max_value=65535)
                smtp_user = st.text_input("SMTP用户名（邮箱）", os.getenv("SMTP_USER", ""))
                smtp_password = st.text_input("SMTP密码/授权码", type="password", value=os.getenv("SMTP_PASSWORD", ""))
                
                if st.button("📤 批量发送邮件"):
                    if not smtp_server or not smtp_user or not smtp_password:
                        st.error("❌ 请先配置SMTP参数")
                    else:
                        try:
                            from backend.services.email_integration import send_email_via_smtp
                            
                            success_count = 0
                            fail_count = 0
                            
                            for invite in invite_results:
                                result = send_email_via_smtp(
                                    to_email=invite.get("email", ""),
                                    subject=f"面试邀约 - {job_title} - {invite.get('name', '')}",
                                    body=invite.get("body", ""),
                                    ics_path=invite.get("ics", ""),
                                    smtp_server=smtp_server,
                                    smtp_port=smtp_port,
                                    smtp_user=smtp_user,
                                    smtp_password=smtp_password,
                                    from_email=smtp_user
                                )
                                
                                if result.get("success"):
                                    success_count += 1
                                else:
                                    fail_count += 1
                                    st.warning(f"❌ {invite.get('name', '')} 发送失败：{result.get('message', '')}")
                            
                            st.success(f"✅ 邮件发送完成：成功 {success_count} 封，失败 {fail_count} 封")
                        except Exception as e:
                            st.error(f"❌ 发送失败：{str(e)}")
            
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

        path = export_round_report(score_source)
        st.success("已导出：" + path)

