import csv
from pathlib import Path
from typing import Dict, Any

def load_job_rules(path: str = "data/templates/岗位配置示例.csv") -> Dict[str, Dict[str, Any]]:
    rules = {}; p = Path(path)
    if not p.exists(): return rules
    with p.open("r", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd: rules[r["job"]] = r
    return rules

def get_job_rule(job: str, rules: Dict[str, Dict[str, Any]]):
    return rules.get(job)

def default_rubric(job: str) -> Dict[str, Any]:
    return {
        "job": job,
        "dimensions": [
            {"name":"专业技能/方法论","weight":0.35},
            {"name":"沟通表达/同理心","weight":0.2},
            {"name":"执行力/主人翁","weight":0.2},
            {"name":"数据意识/结果导向","weight":0.15},
            {"name":"学习成长/潜力","weight":0.1},
        ]
    }

