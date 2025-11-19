import csv
from pathlib import Path
from typing import Dict, Any


def load_job_rules(path: str = "data/templates/岗位配置示例.csv") -> Dict[str, Dict[str, Any]]:
    """从配置 CSV 加载岗位规则，按 job 字段索引。"""
    rules: Dict[str, Dict[str, Any]] = {}
    p = Path(path)

    if not p.exists():
        return rules

    with p.open("r", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            job = r.get("job")
            if job:
                rules[job] = r

    return rules


def get_job_rule(job: str, rules: Dict[str, Dict[str, Any]]):
    """根据岗位名称获取规则。"""
    return rules.get(job)


def default_rubric(job: str) -> Dict[str, Any]:
    """当没有配置时的默认评分维度结构。"""
    return {
        "job": job,
        "dimensions": [
            # {"name":"专业技能/方法论","weight":0.35},
            # {"name":"沟通表达/同理心","weight":0.2},
            # {"name":"执行力/主人翁","weight":0.2},
            # {"name":"数据意识/结果导向","weight":0.15},
            # {"name":"学习成长/潜力","weight":0.1},
        ],
    }
