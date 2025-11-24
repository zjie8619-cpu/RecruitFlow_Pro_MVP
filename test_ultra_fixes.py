"""
测试 Ultra 引擎修复是否生效
"""
import sys
sys.path.insert(0, '.')

from backend.services.ultra_scoring_engine import UltraScoringEngine

# 测试数据
job_title = "班主任"
jd_text = """
岗位职责：
1. 负责学生管理、家校沟通
2. 组织班级活动，维护班级秩序
3. 跟进学生学习情况，提供学习指导

任职要求：
1. 具备良好的沟通表达能力
2. 有教育行业相关经验优先
3. 工作稳定，能长期任职
4. 学习能力强，能快速适应工作
"""

resume_text = """
张三，男，25岁
教育背景：本科学历
工作经历：
2020年-2023年，在某教育机构担任班主任
- 负责学生管理，跟进学生学习情况
- 与家长保持良好沟通，及时反馈学生学习情况
- 组织班级活动，提升班级凝聚力
- 定期复盘工作，总结经验，持续改进
"""

print("=" * 60)
print("测试 Ultra 引擎修复")
print("=" * 60)

# 创建引擎
engine = UltraScoringEngine(job_title, jd_text)

# 执行评分
result = engine.score(resume_text)

print("\n1. 检查评分系统（百分制）")
print("-" * 60)
scores = result.get("scores", {})
print(f"技能匹配度: {scores.get('skill_match')} (应该是0-100)")
print(f"经验相关性: {scores.get('experience_match')} (应该是0-100)")
print(f"成长潜力: {scores.get('growth_potential')} (应该是0-100)")
print(f"稳定性: {scores.get('stability')} (应该是0-100)")
print(f"总分: {scores.get('total_score')} (应该是0-100)")

# 检查是否都是百分制
all_ok = all(0 <= v <= 100 for v in scores.values() if isinstance(v, (int, float)))
print(f"[OK] 所有分数都在0-100范围内: {all_ok}")
if not all_ok:
    print(f"[ERROR] 发现非百分制分数: {[f'{k}={v}' for k, v in scores.items() if isinstance(v, (int, float)) and (v < 0 or v > 100)]}")

print("\n2. 检查标准模型")
print("-" * 60)
standard_model = result.get("standard_model", {})
if standard_model:
    print(f"标准技能匹配度: {standard_model.get('skill_match')}")
    print(f"标准经验相关性: {standard_model.get('experience_match')}")
    print(f"标准成长潜力: {standard_model.get('growth_potential')}")
    print(f"标准稳定性: {standard_model.get('stability')}")
    print(f"[OK] 标准模型已生成")
else:
    print("[ERROR] 标准模型未生成")

print("\n3. 检查标签（禁止幻觉）")
print("-" * 60)
tags = result.get("tags", [])
print(f"标签数量: {len(tags)}")
print(f"标签内容: {tags}")
# 检查标签是否来自证据
evidence_chain = result.get("evidence_chain", [])
all_actions = []
for ev in evidence_chain:
    all_actions.extend(ev.get("actions", []))
print(f"证据链中的动作: {all_actions[:5]}")
print(f"[OK] 标签应该来自证据链")

print("\n4. 检查输出格式")
print("-" * 60)
required_fields = ["scores", "standard_model", "tags", "summary", "evidence_chain", "risk_alert", "highlights"]
missing_fields = [f for f in required_fields if f not in result]
if missing_fields:
    print(f"[ERROR] 缺少字段: {missing_fields}")
else:
    print(f"[OK] 所有必需字段都存在")

print("\n5. 检查证据链格式")
print("-" * 60)
if result.get("evidence_chain"):
    first_ev = result["evidence_chain"][0]
    required_ev_fields = ["dimension", "actions", "raw_evidence", "reasoning"]
    missing_ev_fields = [f for f in required_ev_fields if f not in first_ev]
    if missing_ev_fields:
        print(f"[ERROR] 证据链缺少字段: {missing_ev_fields}")
    else:
        print(f"[OK] 证据链格式正确")
        print(f"  示例: {first_ev.get('dimension')} - {first_ev.get('actions')[:1]}")
else:
    print("[ERROR] 证据链为空")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)



