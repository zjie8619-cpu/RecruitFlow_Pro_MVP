"""
# AI接入模块:支持OpenAI、Claude和硅基流动(SiliconFlow) API调用
"""
import os
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional

def _load_api_keys():
    """从配置文件加载API密钥"""
    keys_file = Path("backend/configs/api_keys.json")
    if keys_file.exists():
        try:
            return json.loads(keys_file.read_text(encoding="utf-8"))
        except:
            return {}
    return {}

def call_openai(prompt: str, model: str = "gpt-4o-mini", temperature: float = 0.7, base_url: Optional[str] = None) -> str:
    """调用OpenAI API(兼容OpenAI格式,包括硅基流动)"""
    try:
        from openai import OpenAI
        # 优先从配置文件读取,其次从环境变量
        api_keys = _load_api_keys()
        api_key = api_keys.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 未配置, 请设置环境变量或在 api_keys.json 中配置。")
        client = OpenAI(
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1"
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature
        )
        return response.choices[0].message.content.strip()
    except ImportError as exc:
        raise ImportError("请安装 openai 包: pip install openai") from exc
    except Exception as e:
        raise Exception(f"OpenAI API调用失败: {str(e)}") from e

def call_siliconflow(prompt: str, model: str = "deepseek-chat", temperature: float = 0.7) -> str:
    """调用硅基流动(SiliconFlow) API"""
    try:
        from openai import OpenAI

        api_key = os.getenv("SILICONFLOW_API_KEY")
        base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")

        if not api_key:
            api_keys = _load_api_keys()
            api_key = api_keys.get("siliconflow_api_key")
            base_url = api_keys.get("siliconflow_base_url", base_url)

        if not api_key:
            raise ValueError(
                "未找到硅基流动 API KEY,请在 backend/configs/api_keys.json 设置 "
                "siliconflow_api_key 或设置环境变量 SILICONFLOW_API_KEY"
            )

        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()

    except ImportError:
        raise ImportError("请安装 openai 包: pip install openai")
    except Exception as e:
        raise Exception(f"硅基流动 API 调用失败: {str(e)}")

def call_claude(prompt: str, model: str = "claude-3-5-sonnet-20241022", temperature: float = 0.7) -> str:
    """调用Claude API"""
    try:
        from anthropic import Anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("未设置 ANTHROPIC_API_KEY 环境变量")
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except ImportError as exc:
        raise ImportError("请安装 anthropic 包: pip install anthropic") from exc
    except Exception as e:
        raise Exception(f"Claude API调用失败: {str(e)}") from e

def generate_jd_with_ai(
    job: str,
    must_have: str = "",
    nice_to_have: str = "",
    exclude_keywords: str = "",
    provider: str = "openai",
    model: Optional[str] = None,
):
    """Generate JD sections via the selected LLM provider."""
    provider = (provider or "openai").lower()
    if provider == "openai":
        model = model or "gpt-4o-mini"
        call_func = call_openai
    elif provider == "claude":
        model = model or "claude-3-5-sonnet-20241022"
        call_func = call_claude
    elif provider == "siliconflow":
        model = model or "deepseek-chat"
        call_func = call_siliconflow
    else:
        raise ValueError("Unsupported AI provider: openai / claude / siliconflow")
    
    info_lines = [
        f"Job Title: {job}",
        f"Must Have: {must_have or 'N/A'}",
        f"Nice To Have: {nice_to_have or 'N/A'}",
        f"Exclude: {exclude_keywords or 'N/A'}",
    ]
    input_info = "\n".join(info_lines)
    
    prompt = f"""
You are a senior recruiter. Create a custom hiring package for "{job}".

[Input]
{input_info}

[Output Requirements]
1. Use === separators in order: LongJD / ShortJD / CompetencyDimensions / InterviewQuestions
2. LongJD must include mission/responsibilities and requirements aligned with the input
3. CompetencyDimensions must be JSON with name/weight/description (5 entries, weights sum to 1)
4. InterviewQuestions must be JSON with dimension/question/evaluation_criteria/weight (weights sum to 1)
5. Use Chinese wording and actionable detail; avoid generic templates

Return only the structured content above.
""".strip()

    
    try:
        response = call_func(prompt, model=model)
        
        # 解析响应
        jd_long = ""
        jd_short = ""
        rubric_dict = {"job": job, "dimensions": []}
        interview_questions = {"questions": []}
        # 灏濊瘯鎸夊垎闅旂瑙ｆ瀽
        if "===" in response:
            segments = [seg.strip() for seg in response.split("===") if seg.strip()]
            if segments:
                jd_long = segments[0]
            if len(segments) > 1:
                jd_short = segments[1]
            for seg in segments:
                start_idx = seg.find('{')
                end_idx = seg.rfind('}') + 1
                if start_idx < 0 or end_idx <= start_idx:
                    continue
                try:
                    payload = json.loads(seg[start_idx:end_idx])
                except json.JSONDecodeError:
                    continue
                if "dimensions" in payload:
                    rubric_dict["dimensions"] = payload["dimensions"]
                if "questions" in payload and payload["questions"]:
                    interview_questions["questions"] = payload["questions"]

        # 如果面试题目没有解析到,尝试从整个响应中查找
        if not interview_questions.get("questions"):
            # 查找所有可能的JSON对象
            json_pattern = r'\{\s*"questions"\s*:\s*\[.*?\]\s*\}'
            matches = re.findall(json_pattern, response, re.DOTALL)
            for match in matches:
                try:
                    questions = json.loads(match)
                    if "questions" in questions and questions["questions"]:
                        interview_questions["questions"] = questions["questions"]
                        break
                except:
                    continue
            
            # 如果还是没找到,尝试查找包含"question"的JSON
            if not interview_questions.get("questions"):
                # 查找包含questions的JSON块
                start_idx = response.find('"questions"')
                if start_idx > 0:
                    # 向前找到最近的{
                    json_start = response.rfind("{", 0, start_idx)
                    # 向后找到匹配的}
                    brace_count = 0
                    json_end = -1
                    for i in range(json_start, len(response)):
                        if response[i] == '{':
                            brace_count += 1
                        elif response[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break
                    if json_end > json_start:
                        try:
                            questions = json.loads(response[json_start:json_end])
                            if "questions" in questions and questions["questions"]:
                                interview_questions["questions"] = questions["questions"]
                        except:
                            pass
        
        # 如果没有解析到,尝试智能提取
        if not jd_long:
            jd_long = response.strip()[:1000]

        if not jd_short:
            jd_short = response.strip()[:200]
        
        # 确保rubric_dict有默认值
        if not rubric_dict.get("dimensions"):
            rubric_dict["dimensions"] = [
#                 {"name": "专业技能/方法论", "weight": 0.35, "description": "专业能力和方法论掌握程度"},
#                 {"name": "沟通表达/同理心", "weight": 0.2, "description": "沟通能力和同理心"},
#                 {"name": "执行力/主人翁", "weight": 0.2, "description": "执行力和主人翁意识"},
#                 {"name": "数据意识/结果导向", "weight": 0.15, "description": "数据意识和结果导向"},
#                 {"name": "学习成长/潜力", "weight": 0.1, "description": "学习能力和成长潜力"}
            ]
        
        # 确保interview_questions有默认值
        if not interview_questions.get("questions"):
            interview_questions["questions"] = [
                {
#                     "dimension": "专业技能",
#                     "question": "请描述一个你解决过的专业问题,说明你的解决思路和方法",
#                     "evaluation_criteria": "优秀:思路清晰,方法得当,有创新;良好:能解决问题但方法常规;一般:思路模糊;不合格:无法回答",
                    "weight": 0.25
                }
            ]
        
        return jd_long, jd_short, rubric_dict, interview_questions
        
    except Exception as e:
        raise Exception(f"AI生成JD失败: {str(e)}") from e

