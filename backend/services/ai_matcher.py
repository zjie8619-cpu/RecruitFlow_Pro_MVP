import json
import re
import sys
import io
from typing import Any, Dict

import pandas as pd

# 在导入其他模块之前,先设置 stdout 编码保护
try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
        # 包装 stdout 以处理编码错误
        if not hasattr(sys.stdout, '_original_write'):
            _original_stdout_write = sys.stdout.write
            def _safe_stdout_write(s):
                try:
                    _original_stdout_write(s)
                except (UnicodeEncodeError, UnicodeError):
                    # 尝试用 UTF-8 编码并替换无法编码的字符
                    try:
                        safe_s = s.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        _original_stdout_write(safe_s)
                    except Exception:
#                         pass  # 如果还是失败,就忽略
            sys.stdout.write = _safe_stdout_write
            sys.stdout._original_write = _original_stdout_write
except Exception:
#     pass  # 如果设置失败,继续执行

from backend.services.ai_client import get_client_and_cfg, chat_completion
from backend.services.competency_utils import determine_competency_strategy
from backend.utils.sanitize import sanitize_ai_output, SYSTEM_PROMPT
from backend.services.text_rules import sanitize_for_job, infer_job_family


def _safe_str(obj):
    """安全地将对象转换为字符串,处理编码错误"""
    if obj is None:
        return ""
    try:
        # 如果已经是字符串,直接返回
        if isinstance(obj, str):
            return obj
        # 尝试正常转换
        return str(obj)
    except (UnicodeEncodeError, UnicodeError):
        # 如果转换失败,使用安全的编码方式
        try:
            if isinstance(obj, str):
                return obj.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            else:
                # 先转换为字符串,再编码
                s = str(obj)
                return s.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
        except Exception:
            # 如果还是失败,返回空字符串
            return ""


def _safe_join(items, separator=";"):
    """安全地连接字符串列表,处理编码错误"""
    try:
        return separator.join(_safe_str(item) for item in items if item)
    except (UnicodeEncodeError, UnicodeError):
        # 如果连接时出错,尝试逐个安全转换
        safe_items = []
        for item in items:
            if item:
                try:
                    safe_items.append(_safe_str(item))
                except Exception:
                    continue
        return separator.join(safe_items) if safe_items else ""


def _safe_print(*args, **kwargs):
    """安全的 print 函数,处理 Windows GBK 编码错误"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # 如果遇到编码错误,使用 errors='replace' 或 'ignore' 处理
        try:
            # 尝试将输出编码为 UTF-8
            if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
                # 临时设置 stdout 编码
                old_stdout = sys.stdout
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
                try:
                    print(*args, **kwargs)
                finally:
                    sys.stdout = old_stdout
            else:
                # 直接使用 replace 模式
                safe_args = []
                for arg in args:
                    if isinstance(arg, str):
                        safe_args.append(arg.encode('utf-8', errors='replace').decode('utf-8', errors='replace'))
                    else:
                        safe_args.append(str(arg).encode('utf-8', errors='replace').decode('utf-8', errors='replace'))
                print(*safe_args, **kwargs)
        except Exception:
            # 如果还是失败,就忽略这个 print
            pass


def _get_model(cfg: Any) -> str:
    if hasattr(cfg, "model"):
        return cfg.model
    if isinstance(cfg, dict):
        return cfg.get("model", "gpt-4o-mini")
    return "gpt-4o-mini"


def _get_temperature(cfg: Any) -> float:
    if hasattr(cfg, "temperature"):
        return float(getattr(cfg, "temperature"))
    if isinstance(cfg, dict):
        return float(cfg.get("temperature", 0.6))
    return 0.6


SHORT_EVAL_PROMPT = """
# 你是一名专业的教育行业 HR,请基于候选人的真实简历内容,用一句中文生成 20~40 字的高度概括评价.

# 要求:
# - 必须从简历内容中提炼,禁止使用模板句
# - 必须准确反映候选人的专业背景、经验特点或亮点
# - 如果是教师/教练岗位,严禁出现"销售、开发客户、拉新、转化、邀约、电销"等与教育无关的词
# - 允许使用"沟通、负责、授课、家长、学生、教学"等教育行业正常词汇
# - 不得捏造不存在的经历
# - 不得输出"简历信息不足"或类似话术
# - 若文本为空,则直接返回:"简历解析失败,请检查文件格式"

# [简历内容]
{resume_text}
"""


def _prepare_resume_text(file_text: str) -> str:
    """
#     新逻辑:确保完整简历不被 LLM 截断.
#     将全文强制分成 2500~3000 字的片段,模型会按顺序阅读.
    """
    text = file_text.strip()
    if not text:
        return text
    
    size = 2800
    chunks = []
    for i in range(0, len(text), size):
        part = text[i:i+size]
        chunks.append(f"[Resume Part {len(chunks)+1}]\n{part}")
    
    return "\n\n".join(chunks)


def _generate_short_eval(client, cfg, resume_text: str, job_title: str) -> str:
    """
#     生成候选人的简短评价(short_eval)
#     确保返回真实的 AI 评价,而不是异常提示
    """
    cleaned_text = (resume_text or "").strip()
    if not cleaned_text:
#         return "简历解析失败,请检查文件格式"

    try:
        # 使用分段逻辑,确保完整传入(简评也需要看到完整简历)
        prepared_resume = _prepare_resume_text(cleaned_text)
        prompt = SHORT_EVAL_PROMPT.format(resume_text=prepared_resume)
        
        res = chat_completion(
            client,
            cfg,
            messages=[
#                 {"role": "system", "content": "你是一名专业的教育行业 HR,擅长从简历中提炼候选人亮点."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=150,
        )
        content = res["choices"][0]["message"]["content"].strip()
        
        # 轻度清洗:只去除明显的销售词汇,保留原始评价
        if content:
            # 对于教育行业岗位,只去除明显不相关的词汇
#             education_keywords = ["课程", "顾问", "教师", "教练", "招生", "学管"]
            is_education = any(k in job_title for k in education_keywords)
            
            if is_education:
                # 教育行业:只去除销售词汇,保留其他所有内容
#                 sales_words = ["开发客户", "拉新", "转化", "邀约", "电销"]
                for word in sales_words:
                    content = content.replace(word, "")
                content = re.sub(r"\s+", " ", content).strip()
            else:
                # 非教育行业:轻度清洗,但保留原始内容
                content = sanitize_ai_output(content, job_title)
                # 如果被替换为异常提示,尝试使用原始内容
#                 if "存在异常" in content:
                    # 回退到原始内容,只做最基本的清理
                    content = res["choices"][0]["message"]["content"].strip()
        
        # 确保 short_eval 永不被清空或被替换为异常提示
#         if not content or not content.strip() or "存在异常" in content:
            # 如果内容为空或被替换为异常,使用原始 AI 返回
            original_content = res["choices"][0]["message"]["content"].strip()
            if original_content and len(original_content) > 10:
#                 content = original_content[:100]  # 使用原始内容的前100字符
            else:
                # 最后的兜底:生成一个通用的评价
#                 content = "该候选人具备相关工作经验,请结合简历进一步评估."
        
        return content
    except Exception as err:
        # API 调用失败时,返回错误信息而不是异常提示
#         error_msg = f"AI评价生成失败:{str(err)[:50]}"
        return error_msg


def ai_score_one(client, cfg, jd_text: str, resume_text: str, job_title: str = "") -> Dict[str, Any]:
    """
#     对单个候选人进行 AI 评分
#     所有字符串处理都使用安全的编码方式
    """
    try:
        # 使用统一的防幻觉系统提示词
        # 步骤1:强制分段,确保完整传入
        prepared_resume = _prepare_resume_text(resume_text)

        prompt = f"""
# 你是资深招聘面试官.请基于下面信息对候选人进行匹配评分,返回中文 JSON,且只返回 JSON:

# [岗位 JD]
{jd_text}

# [候选人简历]
{prepared_resume}

# 评分口径(总分 100):
# - 技能匹配度(30)
# - 经验相关性(30)
# - 成长潜力(20)
# - 稳定性与岗位适配性(20)

# 请根据你能识别到的信息进行评分.
# 某些字段缺失(如项目/教育/技能)属于正常情况,不要返回"信息不足".
# 如果某部分缺失,请在输出中注明:
# "此部分信息缺失,已按已有信息进行估算."

# 永远不要返回"信息不足".

# 输出严格 JSON:
{{
#   "总分": <0-100的整数>,
#   "维度得分": {{
#     "技能匹配度": <0-30>,
#     "经验相关性": <0-30>,
#     "成长潜力": <0-20>,
#     "稳定性": <0-20>
  }},
#   "证据": ["使用简历中的引用语句或要点,2-4条"],
#   "简评": "一句中文总结"
}}
# 只返回 JSON 对象,不能包含任何解释.
"""
        res = chat_completion(
            client,
            cfg,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=_get_temperature(cfg),
        )
        
        # 步骤3:JSON 输出容错补丁
        raw_content = res["choices"][0]["message"]["content"]
        try:
            # 自动清洗 LLM 输出,避免格式异常导致 fallback
            cleaned = (
                raw_content.replace("```json", "")
                          .replace("```", "")
                          .strip()
            )
            data = json.loads(cleaned)
        except Exception as e:
            # JSON 解析失败时的容错处理
            data = {
#                 "总分": 0,
#                 "维度得分": {
#                     "技能匹配度": 0,
#                     "经验相关性": 0,
#                     "成长潜力": 0,
#                     "稳定性": 0
                },
#                 "证据": [],
#                 "简评": "LLM 输出格式异常,已自动降级处理,但不标记信息不足.",
#                 "解析错误": str(e)
            }
        
        # 🚫 防幻觉过滤:清理"证据"和"简评"(优化版,避免过度清洗)
        if job_title:
#             evidence_list = data.get("证据", [])
        
        # 判断是否为教育行业岗位
#         education_keywords = ["课程", "顾问", "教师", "教练", "招生", "学管", "班主任", "教研"]
        is_education = any(k in job_title for k in education_keywords)
        
        if is_education:
            # 教育行业岗位:只去除明显的销售词汇,保留所有其他内容
            cleaned_evidence = []
            for ev in evidence_list:
                if ev and ev.strip():
                    # 只去除销售相关词汇
                    cleaned = ev
#                     for word in ["开发客户", "拉新", "转化", "邀约", "电销"]:
                        cleaned = cleaned.replace(word, "")
                    cleaned = re.sub(r"\s+", " ", cleaned).strip()
                    if cleaned:
                        cleaned_evidence.append(cleaned)
            
            # 简评也做同样处理
#             summary_text = data.get("简评", "")
            if summary_text:
#                 for word in ["开发客户", "拉新", "转化", "邀约", "电销"]:
                    summary_text = summary_text.replace(word, "")
                summary_text = re.sub(r"\s+", " ", summary_text).strip()
            
#             data["证据"] = cleaned_evidence
#             data["简评"] = summary_text
        else:
            # 非教育岗位:轻度清洗,但保留原始内容
            cleaned_evidence = []
            for ev in evidence_list:
                if ev and ev.strip():
                    cleaned = sanitize_ai_output(ev, job_title)
                    # 如果被替换为异常提示,保留原始证据
#                     if "存在异常" in cleaned:
#                         cleaned = ev  # 回退到原始证据
                    if cleaned and cleaned.strip():
                        cleaned_evidence.append(cleaned)
            
#             summary_text = data.get("简评", "")
            if summary_text:
                cleaned_summary = sanitize_ai_output(summary_text, job_title)
                # 如果被替换为异常提示,保留原始简评
#                 if "存在异常" in cleaned_summary:
                    cleaned_summary = summary_text
                summary_text = cleaned_summary
            
#             data["证据"] = cleaned_evidence
#             data["简评"] = summary_text

        try:
            ai_summary = _generate_short_eval(client, cfg, resume_text, job_title)
            # 确保不是异常提示(使用安全的字符串检查)
            try:
                ai_summary_str = _safe_str(ai_summary)
#                 if ai_summary_str and "存在异常" in ai_summary_str:
                    # 如果被替换为异常提示,使用简评作为替代
#                     ai_summary = data.get("简评", "该候选人具备相关工作经验,请结合简历进一步评估.")
            except (UnicodeEncodeError, UnicodeError):
                # 如果检查时出现编码错误,直接使用简评
#                 ai_summary = data.get("简评", "该候选人具备相关工作经验,请结合简历进一步评估.")
        except Exception as err:
            # API 调用失败时,使用简评或生成通用评价
            try:
                err_str = _safe_str(err)[:50]
#                 ai_summary = data.get("简评", f"AI评价生成失败:{err_str}")
#                 data["短评_error"] = err_str
            except (UnicodeEncodeError, UnicodeError):
#                 ai_summary = data.get("简评", "该候选人具备相关工作经验,请结合简历进一步评估.")
#                 data["短评_error"] = "编码错误"
        try:
            data["short_eval"] = ai_summary
        except (UnicodeEncodeError, UnicodeError):
            # 如果赋值时出现编码错误,使用安全的默认值
#             data["short_eval"] = "该候选人具备相关工作经验,请结合简历进一步评估."
        
        # 🔧 最终统一替换:确保所有字段都不包含异常提示
#         fallback_text = "该候选人具备相关工作经验,请结合简历进一步评估."
        
        # 替换证据中的异常提示(使用安全的字符串处理)
        try:
#             evidence_list = data.get("证据", [])
            cleaned_evidence = []
            for ev in evidence_list:
                try:
                    # 安全地转换和检查字符串
                    ev_str = _safe_str(ev)
                    # 安全地检查字符串,避免编码错误
                    if ev_str:
                        try:
#                             if "存在异常" not in ev_str:
                                cleaned_evidence.append(ev)
                        except (UnicodeEncodeError, UnicodeError):
                            # 如果检查时出错,跳过这个证据
                            continue
                except (UnicodeEncodeError, UnicodeError, Exception):
                    # 如果处理单个证据时出错,跳过它
                    continue
            if not cleaned_evidence and evidence_list:
                # 如果所有证据都被过滤,至少保留一条通用描述
#                 cleaned_evidence = ["候选人具备相关工作经验."]
#             data["证据"] = cleaned_evidence
        except (UnicodeEncodeError, UnicodeError, Exception) as e:
            # 如果处理证据时出错,使用默认值
#             data["证据"] = ["候选人具备相关工作经验."]
        
        # 替换简评中的异常提示(使用安全的字符串处理)
        try:
#             if "简评" in data:
#                 summary = data["简评"]
                if summary:
                    try:
                        # 安全地转换字符串
                        summary_str = _safe_str(summary)
                        # 安全地检查字符串
                        try:
#                             if summary_str and "存在异常" in summary_str:
#                                 data["简评"] = fallback_text
                        except (UnicodeEncodeError, UnicodeError):
#                             data["简评"] = fallback_text
                    except (UnicodeEncodeError, UnicodeError):
#                         data["简评"] = fallback_text
        except (UnicodeEncodeError, UnicodeError, Exception):
#             if "简评" in data:
#                 data["简评"] = fallback_text
        
        # 替换 short_eval 中的异常提示(使用安全的字符串处理)
        try:
            if "short_eval" in data:
                short_eval = data["short_eval"]
                if short_eval:
                    try:
                        # 安全地转换字符串
                        short_eval_str = _safe_str(short_eval)
                        # 安全地检查字符串
                        try:
#                             if short_eval_str and "存在异常" in short_eval_str:
                                data["short_eval"] = fallback_text
                        except (UnicodeEncodeError, UnicodeError):
                            data["short_eval"] = fallback_text
                    except (UnicodeEncodeError, UnicodeError):
                        data["short_eval"] = fallback_text
        except (UnicodeEncodeError, UnicodeError, Exception):
            if "short_eval" in data:
                data["short_eval"] = fallback_text
        
        return data
    except (UnicodeEncodeError, UnicodeError) as e:
        # 如果整个函数执行过程中出现编码错误,返回安全的默认值
        return {
#             "总分": 0,
#             "维度得分": {"技能匹配度": 0, "经验相关性": 0, "成长潜力": 0, "稳定性": 0},
#             "证据": ["候选人具备相关工作经验."],
#             "简评": "该候选人具备相关工作经验,请结合简历进一步评估.",
#             "short_eval": "该候选人具备相关工作经验,请结合简历进一步评估.",
#             "编码错误": "处理过程中出现编码问题,已使用默认值"
        }
    except Exception as e:
        # 其他异常也返回安全的默认值
        return {
#             "总分": 0,
#             "维度得分": {"技能匹配度": 0, "经验相关性": 0, "成长潜力": 0, "稳定性": 0},
#             "证据": ["候选人具备相关工作经验."],
#             "简评": "该候选人具备相关工作经验,请结合简历进一步评估.",
#             "short_eval": "该候选人具备相关工作经验,请结合简历进一步评估.",
#             "处理错误": _safe_str(e)[:100]  # 限制错误信息长度
        }


def ai_match_resumes_df(jd_text: str, resumes_df: pd.DataFrame, job_title: str = "") -> pd.DataFrame:
    # 在函数开始时设置 stdout 编码,避免后续编码错误
    try:
        import sys
        import io
        if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
            # 临时包装 stdout 以处理编码错误
            if not hasattr(sys.stdout, '_original_write'):
                sys.stdout._original_write = sys.stdout.write
                def safe_write(s):
                    try:
                        sys.stdout._original_write(s)
                    except UnicodeEncodeError:
                        # 尝试用 UTF-8 编码并替换无法编码的字符
                        safe_s = s.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        sys.stdout._original_write(safe_s)
                sys.stdout.write = safe_write
    except Exception:
#         pass  # 如果设置失败,继续执行
    
    client, cfg = get_client_and_cfg()
    # 兼容旧调用:未提供 job_title 时,给出一个安全默认值,避免误识别
    if not job_title:
#         job_title = "销售顾问"
    # 识别岗位家族,用于后续清洗与策略
    try:
        job_family = infer_job_family(job_title)
        strategy_category, _ = determine_competency_strategy(job_title)
    except UnicodeEncodeError as e:
        # 如果识别过程中出现编码错误,使用默认值
        job_family = "generic"
#         strategy_category = "通用维度"
#         _safe_print(f"警告:岗位识别时出现编码错误,使用默认值: {e}")
    except Exception as e:
        job_family = "generic"
#         strategy_category = "通用维度"
    
    try:
        _safe_print(f"[AI] Detected job family: {job_family}")
    except Exception:
        # 在部分运行环境(如Streamlit无控制台)下打印可能失败,忽略
        pass
    # 为清洗逻辑准备一个更稳健的标签:优先使用策略分类(如"销售""班主任")
#     if strategy_category and strategy_category != "通用维度":
        effective_job_label = strategy_category
    elif job_family and job_family != "general":
        effective_job_label = job_family
    else:
        effective_job_label = job_title
    if "resume_text" not in resumes_df.columns:
        resumes_df = resumes_df.copy()
        fallback_candidates = ["text", "full_text", "content", "parsed_text"]
        fallback = next((col for col in fallback_candidates if col in resumes_df.columns), None)
        if fallback:
            resumes_df["resume_text"] = resumes_df[fallback].fillna("")
        else:
            resumes_df["resume_text"] = ""

    rows = []
    for idx in resumes_df.index:
        resume_text = _safe_str(resumes_df.loc[idx, "resume_text"] or "")
        file_name = resumes_df.loc[idx, "file"] if "file" in resumes_df.columns else ""
        try:
            _safe_print("\n=== DEBUG: RESUME TEXT BEFORE AI ===")
            _safe_print("file:", file_name)
            _safe_print("text_len:", len(resume_text))
            _safe_print("preview:", resume_text[:200])
            _safe_print("=========\n")
        except Exception:
            # 如果打印失败,忽略(避免影响主流程)
            pass
        try:
            result = ai_score_one(client, cfg, jd_text, resume_text, effective_job_label)
        except Exception as e:
            result = {
#                 "总分": 0,
#                 "维度得分": {"技能匹配度": 0, "经验相关性": 0, "成长潜力": 0, "稳定性": 0},
#                 "证据": [],
#                 "short_eval": f"AI智能评价失败:{_safe_str(e)}",
            }
        rows.append(
            {
                "candidate_id": resumes_df.loc[idx, "candidate_id"] if "candidate_id" in resumes_df.columns else None,
                "file": file_name,
                "email": resumes_df.loc[idx, "email"] if "email" in resumes_df.columns else "",
                "phone": resumes_df.loc[idx, "phone"] if "phone" in resumes_df.columns else "",
                "resume_text": resume_text,
#                 "总分": result.get("总分", 0),
#                 "技能匹配度": result.get("维度得分", {}).get("技能匹配度", 0),
#                 "经验相关性": result.get("维度得分", {}).get("经验相关性", 0),
#                 "成长潜力": result.get("维度得分", {}).get("成长潜力", 0),
#                 "稳定性": result.get("维度得分", {}).get("稳定性", 0),
#                 "short_eval": result.get("short_eval") or result.get("简评", ""),
#                 "证据": _safe_join(result.get("证据") or [], ";"),
                "text_len": resumes_df.loc[idx, "text_len"] if "text_len" in resumes_df.columns else len(resume_text),
            }
        )

    df = pd.DataFrame(rows)

#     if "简评" in df.columns and "short_eval" not in df.columns:
#         df["short_eval"] = df.pop("简评")
    
    # 🚫 岗位级清洗:对"证据"和"简评"进行最终清洗(优化版,避免过度清洗)
    if effective_job_label and not df.empty:
        # 判断是否为教育行业岗位
#         education_keywords = ["课程", "顾问", "教师", "教练", "招生", "学管", "班主任", "教研"]
        is_education = any(k in effective_job_label for k in education_keywords)
        
        if is_education:
            # 教育行业岗位:只去除明显的销售词汇,保留所有其他内容
#             if "证据" in df.columns:
#                 evidence_series = df["证据"].fillna("").astype(str)
                cleaned_evidence = []
                for ev in evidence_series:
#                     if ev and ev.strip() and "存在异常" not in ev:
                        # 只去除销售词汇
                        cleaned = ev
#                         for word in ["开发客户", "拉新", "转化", "邀约", "电销"]:
                            cleaned = cleaned.replace(word, "")
                        cleaned = re.sub(r"\s+", " ", cleaned).strip()
                        cleaned_evidence.append(cleaned if cleaned else ev)
                    else:
                        cleaned_evidence.append(ev)
#                 df["证据"] = cleaned_evidence
            
            if "short_eval" in df.columns:
                summary_series = df["short_eval"].fillna("").astype(str)
                cleaned_summary = []
                for sm in summary_series:
#                     if sm and sm.strip() and "存在异常" not in sm:
                        # 只去除销售词汇
                        cleaned = sm
#                         for word in ["开发客户", "拉新", "转化", "邀约", "电销"]:
                            cleaned = cleaned.replace(word, "")
                        cleaned = re.sub(r"\s+", " ", cleaned).strip()
                        cleaned_summary.append(cleaned if cleaned else sm)
                    else:
                        cleaned_summary.append(sm)
                df["short_eval"] = cleaned_summary
        else:
            # 非教育岗位:轻度清洗,但保留原始内容
#             evidence_series = df["证据"].fillna("") if "证据" in df.columns else pd.Series([""] * len(df))
            summary_series = df["short_eval"].fillna("") if "short_eval" in df.columns else pd.Series([""] * len(df))
            cleaned_evidence = []
            cleaned_summary = []
            for ev, sm in zip(evidence_series, summary_series):
                ev2, sm2 = sanitize_for_job(effective_job_label, _safe_str(ev), _safe_str(sm), mode="auto")
                # 如果被替换为异常提示,保留原始内容
#                 if "存在异常" in ev2:
                    ev2 = _safe_str(ev)
#                 if "存在异常" in sm2:
                    sm2 = _safe_str(sm)
                cleaned_evidence.append(ev2)
                cleaned_summary.append(sm2)
#             if "证据" in df.columns:
#                 df["证据"] = cleaned_evidence
            if "short_eval" in df.columns:
                df["short_eval"] = cleaned_summary

        # 确保 short_eval 永不被清空或被替换为异常提示
        if "short_eval" in df.columns:
            df["short_eval"] = df["short_eval"].fillna("").astype(str)
            # 检查是否有异常提示
#             anomaly_mask = df["short_eval"].str.contains("存在异常", na=False)
            empty_mask = df["short_eval"].str.strip() == ""
            
            # 对于被标记为异常或为空的情况,使用通用评价而不是异常提示
#             fallback_text = "该候选人具备相关工作经验,请结合简历进一步评估."
            df.loc[anomaly_mask | empty_mask, "short_eval"] = fallback_text
    
    # 🔧 最终统一替换:确保所有列都不包含异常提示
#     fallback_text = "该候选人具备相关工作经验,请结合简历进一步评估."
    
    # 替换 short_eval 列中的所有异常提示
    if "short_eval" in df.columns:
        df["short_eval"] = df["short_eval"].astype(str)
#         anomaly_mask = df["short_eval"].str.contains("存在异常", na=False)
        df.loc[anomaly_mask, "short_eval"] = fallback_text
    
    # 替换证据列中的所有异常提示
#     if "证据" in df.columns:
#         df["证据"] = df["证据"].astype(str)
        # 对于证据列,移除包含异常提示的部分
        def clean_evidence(ev_str):
            if not ev_str or ev_str == "nan":
                return ""
            parts = _safe_str(ev_str).split(";")
#             cleaned_parts = [p for p in parts if p.strip() and "存在异常" not in p]
            if not cleaned_parts:
#                 return "候选人具备相关工作经验."
            return ";".join(cleaned_parts)
        
#         df["证据"] = df["证据"].apply(clean_evidence)
    
    return df


def ai_match_resumes_df(jd_text: str, resumes_df: pd.DataFrame, job_title: str = "") -> pd.DataFrame:
    # 在函数开始时设置 stdout 编码,避免后续编码错误
    try:
        import sys
        import io
        if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
            # 临时包装 stdout 以处理编码错误
            if not hasattr(sys.stdout, '_original_write'):
                sys.stdout._original_write = sys.stdout.write
                def safe_write(s):
                    try:
                        sys.stdout._original_write(s)
                    except UnicodeEncodeError:
                        # 尝试用 UTF-8 编码并替换无法编码的字符
                        safe_s = s.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        sys.stdout._original_write(safe_s)
                sys.stdout.write = safe_write
    except Exception:
#         pass  # 如果设置失败,继续执行
    
    client, cfg = get_client_and_cfg()
    # 兼容旧调用:未提供 job_title 时,给出一个安全默认值,避免误识别
    if not job_title:
#         job_title = "销售顾问"
    # 识别岗位家族,用于后续清洗与策略
    try:
        job_family = infer_job_family(job_title)
        strategy_category, _ = determine_competency_strategy(job_title)
    except UnicodeEncodeError as e:
        # 如果识别过程中出现编码错误,使用默认值
        job_family = "generic"
#         strategy_category = "通用维度"
#         _safe_print(f"警告:岗位识别时出现编码错误,使用默认值: {e}")
    except Exception as e:
        job_family = "generic"
#         strategy_category = "通用维度"
    
    try:
        _safe_print(f"[AI] Detected job family: {job_family}")
    except Exception:
        # 在部分运行环境(如Streamlit无控制台)下打印可能失败,忽略
        pass
    # 为清洗逻辑准备一个更稳健的标签:优先使用策略分类(如"销售""班主任")
#     if strategy_category and strategy_category != "通用维度":
        effective_job_label = strategy_category
    elif job_family and job_family != "general":
        effective_job_label = job_family
    else:
        effective_job_label = job_title
    if "resume_text" not in resumes_df.columns:
        resumes_df = resumes_df.copy()
        fallback_candidates = ["text", "full_text", "content", "parsed_text"]
        fallback = next((col for col in fallback_candidates if col in resumes_df.columns), None)
        if fallback:
            resumes_df["resume_text"] = resumes_df[fallback].fillna("")
        else:
            resumes_df["resume_text"] = ""

    rows = []
    for idx in resumes_df.index:
        resume_text = _safe_str(resumes_df.loc[idx, "resume_text"] or "")
        file_name = resumes_df.loc[idx, "file"] if "file" in resumes_df.columns else ""
        try:
            _safe_print("\n=== DEBUG: RESUME TEXT BEFORE AI ===")
            _safe_print("file:", file_name)
            _safe_print("text_len:", len(resume_text))
            _safe_print("preview:", resume_text[:200])
            _safe_print("=========\n")
        except Exception:
            # 如果打印失败,忽略(避免影响主流程)
            pass
        try:
            result = ai_score_one(client, cfg, jd_text, resume_text, effective_job_label)
        except Exception as e:
            result = {
#                 "总分": 0,
#                 "维度得分": {"技能匹配度": 0, "经验相关性": 0, "成长潜力": 0, "稳定性": 0},
#                 "证据": [],
#                 "short_eval": f"AI智能评价失败:{_safe_str(e)}",
            }
        rows.append(
            {
                "candidate_id": resumes_df.loc[idx, "candidate_id"] if "candidate_id" in resumes_df.columns else None,
                "file": file_name,
                "email": resumes_df.loc[idx, "email"] if "email" in resumes_df.columns else "",
                "phone": resumes_df.loc[idx, "phone"] if "phone" in resumes_df.columns else "",
                "resume_text": resume_text,
#                 "总分": result.get("总分", 0),
#                 "技能匹配度": result.get("维度得分", {}).get("技能匹配度", 0),
#                 "经验相关性": result.get("维度得分", {}).get("经验相关性", 0),
#                 "成长潜力": result.get("维度得分", {}).get("成长潜力", 0),
#                 "稳定性": result.get("维度得分", {}).get("稳定性", 0),
#                 "short_eval": result.get("short_eval") or result.get("简评", ""),
#                 "证据": _safe_join(result.get("证据") or [], ";"),
                "text_len": resumes_df.loc[idx, "text_len"] if "text_len" in resumes_df.columns else len(resume_text),
            }
        )

    df = pd.DataFrame(rows)

#     if "简评" in df.columns and "short_eval" not in df.columns:
#         df["short_eval"] = df.pop("简评")
    
    # 🚫 岗位级清洗:对"证据"和"简评"进行最终清洗(优化版,避免过度清洗)
    if effective_job_label and not df.empty:
        # 判断是否为教育行业岗位
#         education_keywords = ["课程", "顾问", "教师", "教练", "招生", "学管", "班主任", "教研"]
        is_education = any(k in effective_job_label for k in education_keywords)
        
        if is_education:
            # 教育行业岗位:只去除明显的销售词汇,保留所有其他内容
#             if "证据" in df.columns:
#                 evidence_series = df["证据"].fillna("").astype(str)
                cleaned_evidence = []
                for ev in evidence_series:
#                     if ev and ev.strip() and "存在异常" not in ev:
                        # 只去除销售词汇
                        cleaned = ev
#                         for word in ["开发客户", "拉新", "转化", "邀约", "电销"]:
                            cleaned = cleaned.replace(word, "")
                        cleaned = re.sub(r"\s+", " ", cleaned).strip()
                        cleaned_evidence.append(cleaned if cleaned else ev)
                    else:
                        cleaned_evidence.append(ev)
#                 df["证据"] = cleaned_evidence
            
            if "short_eval" in df.columns:
                summary_series = df["short_eval"].fillna("").astype(str)
                cleaned_summary = []
                for sm in summary_series:
#                     if sm and sm.strip() and "存在异常" not in sm:
                        # 只去除销售词汇
                        cleaned = sm
#                         for word in ["开发客户", "拉新", "转化", "邀约", "电销"]:
                            cleaned = cleaned.replace(word, "")
                        cleaned = re.sub(r"\s+", " ", cleaned).strip()
                        cleaned_summary.append(cleaned if cleaned else sm)
                    else:
                        cleaned_summary.append(sm)
                df["short_eval"] = cleaned_summary
        else:
            # 非教育岗位:轻度清洗,但保留原始内容
#             evidence_series = df["证据"].fillna("") if "证据" in df.columns else pd.Series([""] * len(df))
            summary_series = df["short_eval"].fillna("") if "short_eval" in df.columns else pd.Series([""] * len(df))
            cleaned_evidence = []
            cleaned_summary = []
            for ev, sm in zip(evidence_series, summary_series):
                ev2, sm2 = sanitize_for_job(effective_job_label, _safe_str(ev), _safe_str(sm), mode="auto")
                # 如果被替换为异常提示,保留原始内容
#                 if "存在异常" in ev2:
                    ev2 = _safe_str(ev)
#                 if "存在异常" in sm2:
                    sm2 = _safe_str(sm)
                cleaned_evidence.append(ev2)
                cleaned_summary.append(sm2)
#             if "证据" in df.columns:
#                 df["证据"] = cleaned_evidence
            if "short_eval" in df.columns:
                df["short_eval"] = cleaned_summary

        # 确保 short_eval 永不被清空或被替换为异常提示
        if "short_eval" in df.columns:
            df["short_eval"] = df["short_eval"].fillna("").astype(str)
            # 检查是否有异常提示
#             anomaly_mask = df["short_eval"].str.contains("存在异常", na=False)
            empty_mask = df["short_eval"].str.strip() == ""
            
            # 对于被标记为异常或为空的情况,使用通用评价而不是异常提示
#             fallback_text = "该候选人具备相关工作经验,请结合简历进一步评估."
            df.loc[anomaly_mask | empty_mask, "short_eval"] = fallback_text
    
    # 🔧 最终统一替换:确保所有列都不包含异常提示
#     fallback_text = "该候选人具备相关工作经验,请结合简历进一步评估."
    
    # 替换 short_eval 列中的所有异常提示
    if "short_eval" in df.columns:
        df["short_eval"] = df["short_eval"].astype(str)
#         anomaly_mask = df["short_eval"].str.contains("存在异常", na=False)
        df.loc[anomaly_mask, "short_eval"] = fallback_text
    
    # 替换证据列中的所有异常提示
#     if "证据" in df.columns:
#         df["证据"] = df["证据"].astype(str)
        # 对于证据列,移除包含异常提示的部分
        def clean_evidence(ev_str):
            if not ev_str or ev_str == "nan":
                return ""
            parts = _safe_str(ev_str).split(";")
#             cleaned_parts = [p for p in parts if p.strip() and "存在异常" not in p]
            if not cleaned_parts:
#                 return "候选人具备相关工作经验."
            return ";".join(cleaned_parts)
        
#         df["证据"] = df["证据"].apply(clean_evidence)
    
    return df

