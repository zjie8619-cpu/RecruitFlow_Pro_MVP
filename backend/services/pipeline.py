import uuid, json, time
import pandas as pd
from pathlib import Path
from backend.storage.db import get_db, init_db
from backend.utils.audit import audit_log
from backend.core.rules import load_job_rules, get_job_rule, default_rubric
from backend.core.parser import parse_text_resume
from backend.core.scoring import compute_scores
from backend.core.llm import generate_jd_with_ai

class RecruitPipeline:
    def __init__(self, db_path: str = "backend/storage/recruitflow.db", cfg_path: str = "backend/configs/model_config.json"):
        self.db_path = db_path
        self.cfg_path = Path(cfg_path)
        self.cfg = json.loads(self.cfg_path.read_text(encoding="utf-8"))
        init_db()

    def generate_jd(self, job: str, must_have: str = "", nice_to_have: str = "", exclude_keywords: str = "", use_ai: bool = None):
        """
#         生成JD,支持AI智能生成
        
        Args:
#             job: 岗位名称
#             must_have: 必备经验/技能
#             nice_to_have: 加分项
#             exclude_keywords: 排除项
#             use_ai: 是否使用AI(None时根据配置自动判断)
        
        Returns:
            (jd_long, jd_short, rubric_dict, interview_questions)
        """
        # 判断是否使用AI
        if use_ai is None:
            use_ai = self.cfg.get("llm_provider") in ["SiliconFlow", "claude", "siliconflow"]
        
        # 如果启用AI,尝试使用AI生成
        if use_ai:
            try:
                provider = self.cfg.get("llm_provider", "SiliconFlow")
                model = self.cfg.get("llm_model")
                jd_long, jd_short, rubric, interview_questions = generate_jd_with_ai(
                    job, must_have=must_have, nice_to_have=nice_to_have, 
                    exclude_keywords=exclude_keywords, provider=provider, model=model
                )
                audit_log("generate_jd_ai", {"job": job, "provider": provider})
                return jd_long, jd_short, rubric, interview_questions
            except Exception as e:
                # AI失败时回退到离线模式
                audit_log("generate_jd_ai_fallback", {"job": job, "error": str(e)})
                # 继续执行离线逻辑
        
        # 离线模式:从配置文件读取规则
        rules = load_job_rules()
        r = get_job_rule(job, rules) or {}
        must = r.get("must_have","")
        nice = r.get("nice_to_have","")
        exclude = r.get("exclude_keywords","")
#         jd_long = f"""[{job}｜岗位职责]


# 1)面向线上教育学员,完成需求挖掘、课程匹配与转化;
# 2)基于CRM 跟进线索,推进试听课与签约;
# 3)与教研/运营协作,保障服务满意度与续费;
# 4)数据驱动复盘,持续优化转化话术;

# [任职要求]

# 必备:{must or "沟通力强;结果导向;自驱力强"}

# 加分:{nice or "在线教育经验;数据意识;熟悉CRM"}

# 排除:{exclude or "短期实习;频繁跳槽"}
# """
#         jd_short = f"{job}｜高转化话术 + 稳定客源 + 成长路径"
        rubric = default_rubric(job)
        interview_questions = {"questions": []}
        return jd_long, jd_short, rubric, interview_questions

    def save_jd(self, job, jd_long, jd_short, rubric, interview_questions=None):
        conn = get_db(); cur = conn.cursor()
        # 将面试题目合并到rubric中保
        rubric_with_questions = rubric.copy()
        if interview_questions:
            rubric_with_questions["interview_questions"] = interview_questions.get("questions", [])
        cur.execute("INSERT INTO jd (id, job, jd_long, jd_short, rubric_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), job, jd_long, jd_short, json.dumps(rubric_with_questions, ensure_ascii=False), time.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); conn.close(); audit_log("save_jd", {"job":job})

    def ingest_resumes_df(self, df: pd.DataFrame):
        expected = {"name","email","phone","edu","companies","years","skills","projects","text_raw"}
        for c in expected - set(df.columns):
            df[c] = ""
        conn = get_db(); cur = conn.cursor()
        insert_sql = (
            "INSERT INTO resume (id,name,email,phone,edu,companies,years,skills,projects,text_raw,source,created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for _, row in df.iterrows():
            cur.execute(
                insert_sql,
                (
                    str(uuid.uuid4()),
                    str(row["name"]),
                    str(row["email"]),
                    str(row["phone"]),
                    str(row["edu"]),
                    str(row["companies"]),
                    float(row["years"] or 0),
                    str(row["skills"]),
                    str(row["projects"]),
                    str(row["text_raw"]),
                    "csv",
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
        conn.commit(); conn.close(); audit_log("ingest_resumes_df", {"count": len(df)})

    def ingest_text_resume(self, txt: str):
        parsed = parse_text_resume(txt)
        conn = get_db(); cur = conn.cursor()
        insert_sql = (
            "INSERT INTO resume (id,name,email,phone,edu,companies,years,skills,projects,text_raw,source,created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        cur.execute(
            insert_sql,
            (
                str(uuid.uuid4()),
                parsed.get("name", ""),
                parsed.get("email", ""),
                parsed.get("phone", ""),
                parsed.get("edu", ""),
                "",
                float(parsed.get("years") or 0.0),
                "",
                "",
                txt,
                "txt",
                time.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit(); conn.close(); audit_log("ingest_text_resume", {"len": len(txt)})

    def score_all(self, job: str) -> pd.DataFrame:
        cfg = self.cfg
        rules = load_job_rules()
        jr = get_job_rule(job, rules)
#         if not jr: raise ValueError(f"未找到岗位规则:{job}")

        weights = cfg["scoring_weights"]
        wl = cfg.get("company_bias_whitelist", [])
        evidence_max = cfg.get("evidence_max", 3)
        thr = cfg.get("confidence_threshold", 0.65)

        conn = get_db()
        df = pd.read_sql_query("SELECT * FROM resume", conn)
        conn.close()
#         if df.empty: raise ValueError("数据库暂无简历,请先导入")

        rows=[]
        for _, r in df.iterrows():
            score_dict, evidence, conf = compute_scores(jr, r.to_dict(), weights, wl, evidence_max)
            blocked = conf < thr
            rows.append({**r.to_dict(), **score_dict, "evidence":" | ".join(evidence), "confidence": conf, "blocked_by_threshold": blocked})
        out = pd.DataFrame(rows).sort_values(by=["blocked_by_threshold","score_total"], ascending=[True, False]).reset_index(drop=True)

        insert_sql = (
            "INSERT INTO score (id,resume_id,job,score_total,skill_fit,exp_relevance,stability,growth,evidence_json,confidence,created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        conn = get_db(); cur = conn.cursor()
        for _, row in out.iterrows():
            cur.execute(
                insert_sql,
                (
                    str(uuid.uuid4()),
                    row["id"],
                    job,
                    float(row["score_total"]),
                    float(row["skill_fit"]),
                    float(row["exp_relevance"]),
                    float(row["stability"]),
                    float(row["growth"]),
                    json.dumps({"evidence": row["evidence"]}, ensure_ascii=False),
                    float(row["confidence"]),
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
        conn.commit(); conn.close(); audit_log("score_all", {"job":job, "count": len(out)})
        return out

    def dedup_and_rank(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        对候选人结果去重并按得分排序，自动识别常见的得分列名。
        """

        possible_cols = ["score_total", "总分", "score", "match_score", "AI_score"]
        score_col = next((col for col in possible_cols if col in df.columns), None)

        if not score_col:
            raise KeyError(f"未找到评分列, 请确认包含以下任一字段: {possible_cols}")

        if "file" in df.columns:
            df = df.drop_duplicates(subset=["file"], keep="first")
        elif "candidate_id" in df.columns:
            df = df.drop_duplicates(subset=["candidate_id"], keep="first")

        df = df.sort_values(score_col, ascending=False).reset_index(drop=True)
        df["rank"] = df.index + 1

        audit_log("dedup_and_rank", {"remain": len(df)})
        return df

