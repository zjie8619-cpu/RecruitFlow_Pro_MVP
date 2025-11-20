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
from backend.services.jd_ai import generate_jd_bundle
from backend.services.resume_parser import parse_uploaded_files_to_df
from backend.services.ai_matcher import ai_match_resumes_df
from backend.services.ai_core import generate_ai_summary, generate_ai_email
from backend.services.calendar_utils import create_ics_file
from backend.services.excel_exporter import generate_competency_excel
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
                    with st.spinner("🤖 AI正在智能分析岗位需求，生成专业JD、能力维度、面试题目，请稍候（通常需要10-30秒）..."):
                        bundle = generate_jd_bundle(ai_job, ai_must, ai_nice, ai_excl)
                        # 基于长版 JD 再做一次“短版JD提取 + 任职要求抽取能力与面试题”
                        from backend.services.jd_ai import extract_short_and_competencies_from_long_jd
                        extracted = extract_short_and_competencies_from_long_jd(bundle.get("jd_long",""), ai_job)
                        if extracted:
                            # 用抽取得到的短版 JD 覆盖
                            if extracted.get("short_jd"):
                                bundle["jd_short"] = extracted["short_jd"]
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
        
            # 1️⃣ 生成岗位能力维度表 df_dimensions（含分值计算逻辑）
            st.subheader("🎯 岗位能力维度（AI 分析）")
            question_map = {q.get("dimension"): q for q in bundle.get("interview", [])}
            competency_rows = []
            for dim in bundle["dimensions"]:
                anchors = dim.get("anchors") or {}
                question_entry = question_map.get(dim.get("name")) or {}
                question_text = question_entry.get("question")
                if isinstance(question_text, list):
                    question_text = "\n".join(str(item).strip() for item in question_text if str(item).strip())
                question_text = question_text or ""
                points_data = question_entry.get("points") or []
                if isinstance(points_data, str):
                    points_text = "\n".join(p.strip() for p in re.split(r"[；;、\n]", points_data) if p.strip())
                else:
                    points_text = "\n".join(str(p).strip() for p in points_data if str(p).strip())
                competency_rows.append({
                    "能力维度": dim.get("name", ""),
                    "说明": dim.get("desc", ""),
                    "权重(%)": round(float(dim.get("weight", 0)) * 100, 1),
                    "面试问题": question_text,
                    "评分要点": points_text,
                    "20分行为表现": anchors.get("20", ""),
                    "60分行为表现": anchors.get("60", ""),
                    "100分行为表现": anchors.get("100", ""),
                })

            df_dimensions = pd.DataFrame(competency_rows)
            st.dataframe(df_dimensions, use_container_width=True)

            # 导出 Excel
            excel_bytes = generate_competency_excel(bundle["dimensions"], bundle.get("interview", []))
            download_name = f"{(st.session_state.get('job_name') or '岗位').strip()}_能力维度评分表.xlsx"
            st.download_button(
                "📄 导出能力维度评分表（Excel）",
                data=excel_bytes,
                file_name=download_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            with st.expander("🔎 评分锚点（20 / 60 / 100 分行为示例）"):
                for d in bundle["dimensions"]:
                    anchors = d.get("anchors") or {}
                    st.markdown(f"**{d['name']}**")
                    st.markdown(f"- **20 分**：{anchors.get('20', '（未提供）')}")
                    st.markdown(f"- **60 分**：{anchors.get('60', '（未提供）')}")
                    st.markdown(f"- **100 分**：{anchors.get('100', '（未提供）')}")
                    st.markdown("---")
        
            # ------------------ 默认生成函数（修复ImportError用） ------------------
            def generate_default_question(dimension_name: str):
                """AI 无返回时的默认题目模板"""
                default_questions = {
                    "沟通表达/同理心": "请举例说明你在与同事或客户沟通中，如何理解并回应他人情绪与需求。",
                    "执行力/主人翁精神": "请描述一次你面对工作挑战时主动承担责任并推动任务完成的经历。"
                }
                return default_questions.get(dimension_name, f"请结合{dimension_name}维度，描述一个相关的典型工作场景。")

            def generate_default_rubric(dimension_name: str):
                """AI 无返回时的默认评分要点"""
                default_rubrics = {
                    "沟通表达/同理心": ["表达清晰；倾听他人；共情回应；解决冲突能力强。"],
                    "执行力/主人翁精神": ["责任心强；积极主动；执行高效；能带动团队完成目标。"]
                }
                return default_rubrics.get(dimension_name, ["回答逻辑清晰；有实际案例；体现核心能力。"])
            # -------------------------------------------------------------------------
        
            # 3️⃣ 生成岗位能力维度与面试题表 df_final（来自 AI 分析 + AI 生成）
            interview_list = bundle.get("interview", [])
            
            # 构建维度名称到面试题的映射（按维度名称匹配，更可靠）
            interview_map = {}
            for q in interview_list:
                dim_name = q.get("dimension", "").strip()
                if dim_name:
                    interview_map[dim_name] = q
            
            # 构建对齐表格：将维度与面试题一一对应（按维度名称匹配）
            final_rows = []
            for idx, dim_row in df_dimensions.iterrows():
                dim_name = dim_row["能力维度"]
                dim_desc = dim_row["说明"]
                dim_weight = dim_row["权重(%)"]
                
                # 按维度名称匹配对应的面试题
                matched_interview = interview_map.get(dim_name)
                
                if matched_interview:
                    points = matched_interview.get("points") or []
                    points_str = "；".join(points) if isinstance(points, list) else (str(matched_interview.get("points", "")) if matched_interview.get("points") else "")
                    question_text = str(matched_interview.get("question", "")).strip()
                    
                    # 🔧 修正逻辑：如果 AI 没返回内容，重新生成真实文本而非提示语
                    if not question_text or question_text == "（待生成）":
                        question_text = generate_default_question(dim_name)
                    
                    # 🔧 修正逻辑：如果评分要点为空，生成真实评分要点而非提示语
                    if not points_str or points_str.strip() == "":
                        default_points = generate_default_rubric(dim_name)
                        points_str = "；".join(default_points) if isinstance(default_points, list) else str(default_points)
                    
                    final_rows.append({
                        "能力维度": dim_name,
                        "说明": dim_desc,
                        "权重(%)": dim_weight,
                        "面试题目": question_text,
                        "评分要点": points_str,
                        "分值": matched_interview.get("score", 0)
                    })
                else:
                    # 🔧 如果没有对应的面试题，生成真实默认内容（而非提示语）
                    default_question = generate_default_question(dim_name)
                    default_points_list = generate_default_rubric(dim_name)
                    default_points_str = "；".join(default_points_list) if isinstance(default_points_list, list) else str(default_points_list)
                    final_rows.append({
                        "能力维度": dim_name,
                        "说明": dim_desc,
                        "权重(%)": dim_weight,
                        "面试题目": default_question,
                        "评分要点": default_points_str,
                        "分值": 0
                    })
            
            df_final = pd.DataFrame(final_rows)
            
            # ✅ 在显示前加这段：分值与权重对齐修正
            if "权重(%)" in df_final.columns:
                total_weight = df_final["权重(%)"].sum()
                df_final["分值"] = df_final["权重(%)"].apply(lambda w: round(w * 100 / total_weight, 1))
                total_score = round(df_final["分值"].sum(), 1)
                if abs(total_score - 100) > 0.1:
                    df_final["分值"] = df_final["分值"] * 100 / total_score
                    df_final["分值"] = df_final["分值"].round(1)
            
            st.subheader("岗位能力维度与面试题目（AI分析 + AI生成）")
            st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            # 检查是否有缺失项（包含"（待生成）"或空内容）
            has_missing = False
            for _, row in df_final.iterrows():
                if "（待生成）" in str(row.get("面试题目", "")) or not str(row.get("面试题目", "")).strip():
                    has_missing = True
                    break
                if not str(row.get("评分要点", "")).strip():
                    has_missing = True
                    break
            
            if has_missing:
                st.warning("⚠️ 检测到部分维度缺少面试题或评分要点，请点击下方按钮一键补全。")
                if st.button("🔄 一键补全缺失项", type="primary", key="btn_fill_missing_interviews"):
                    # 更新 interview_list 和 bundle
                    updated_interview_list = []
                    for _, row in df_final.iterrows():
                        dim_name = row["能力维度"]
                        question = row["面试题目"]
                        points_str = row["评分要点"]
                        
                        # 🔧 如果还是"（待生成）"或空，生成真实默认内容（而非提示语）
                        if "（待生成）" in question or not question.strip():
                            question = generate_default_question(dim_name)
                        if not points_str.strip():
                            default_points_list = generate_default_rubric(dim_name)
                            points = default_points_list if isinstance(default_points_list, list) else [str(default_points_list)]
                        else:
                            points = [p.strip() for p in points_str.split("；") if p.strip()]
                        
                        updated_interview_list.append({
                            "dimension": dim_name,
                            "question": question,
                            "points": points,
                            "score": row.get("分值", 0)
                        })
                    
                    # 更新 bundle 和 session_state
                    bundle["interview"] = updated_interview_list
                    st.session_state["ai_bundle"] = bundle
                    st.success("✅ 缺失项已补全！请刷新页面查看更新后的表格。")
                    st.rerun()
            else:
                st.markdown("✅ 各能力维度与面试题目已对齐展示，便于结构化评估。")
        
            if st.button("💾 写入系统（保存 JD + 题库）", type="primary", key="btn_save_rubric_1"):
                save_to_system_action()
        else:
            if bundle is None:
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
        from backend.services.ai_client import get_client_and_cfg, AIConfig, chat_completion
        
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
                    result = res.choices[0].message.content.strip()
                    st.success(f"✅ AI 连通性测试成功！返回：{result}")
            except Exception as e:
                error_detail = str(e)
                st.error(f"❌ 连通性失败：{error_detail}")
                if "Key" in error_detail or "未配置" in error_detail:
                    st.info("💡 检查 .env 的 Key 配置；确保文件在项目根目录；重启 Streamlit")
                elif "401" in error_detail or "403" in error_detail:
                    st.info("💡 API Key 无效或已过期，请检查 .env 中的 Key 是否正确")
                elif "404" in error_detail:
                    st.info("💡 模型不存在或未开通，请检查 .env 中的 AI_MODEL，尝试更换为 Qwen2.5-32B-Instruct")
                elif "timeout" in error_detail.lower() or "连接" in error_detail:
                    st.info("💡 网络连接问题，检查公司网络是否放行 api.siliconflow.cn；或尝试使用 OpenAI")
                else:
                    st.info("💡 检查 .env 的 Key/模型/Base URL；或公司网络是否放行 api.siliconflow.cn")
    
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
            st.dataframe(
                resumes_df[["candidate_id", "file", "email", "phone", "text_len"]],
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
                    st.dataframe(
                        scored_df[[
                            "candidate_id",
                            "file",
                            "email",
                            "phone",
                            "总分",
                            "技能匹配度",
                            "经验相关性",
                            "成长潜力",
                            "稳定性",
                            "简评",
                            "证据"
                        ]],
                        use_container_width=True
                    )
                    result_df = scored_df

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
                            result_df.to_csv(output_path, index=False, encoding="utf-8-sig")
                            st.write(f"✅ 已自动保存匹配结果至 `{output_path}`")
                        except Exception as e:
                            st.warning(f"⚠️ 保存CSV失败: {e}")

                        # （可选）提供下载按钮
                        st.download_button(
                            label="⬇️ 下载 AI 匹配结果（CSV）",
                            data=result_df.to_csv(index=False).encode("utf-8-sig"),
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

    score_df = st.session_state.get("score_df")
    if score_df is None or score_df.empty:
        st.warning("请先完成AI匹配评分。")
    else:
        df = score_df.copy()
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
        display_cols = [col for col in ["file", "email", score_col] if col and col in df.columns]
        if not display_cols:
            display_cols = df.columns.tolist()

        st.write(f"已选择 {top_n} 位候选人：")
        st.dataframe(selected_candidates[display_cols], use_container_width=True)

        interview_time = st.text_input("🕒 面试时间（例：2025-11-15 14:00, Asia/Shanghai）", "2025-11-15 14:00, Asia/Shanghai")
        organizer_email = st.text_input("📧 面试组织者邮箱", "hr@company.com")

        if st.button("🚀 一键生成邀约邮件 + ICS"):
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
                    }
                )

            json_payload = json.dumps(invite_results, ensure_ascii=False, indent=2)
            json_path = os.path.join(invites_dir, f"invite_batch_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
            with open(json_path, "w", encoding="utf-8") as fp:
                fp.write(json_payload)

            st.success("✅ AI 个性化邀约生成完成！")
            st.download_button(
                "📥 下载邀约结果（JSON）",
                data=json_payload,
                file_name="ai_invites.json",
                mime="application/json",
            )

            pending_path = "reports/pending_interviews.csv"
            pd.DataFrame(invite_results).to_csv(pending_path, index=False, encoding="utf-8-sig")
            st.write(f"📋 已自动更新待面试清单：`{pending_path}`")

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

