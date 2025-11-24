"""
Ultra引擎调试脚本
用于诊断问题
"""

import sys
sys.path.insert(0, '.')

from backend.services.ultra_scoring_engine import UltraScoringEngine

# 测试简历文本
test_resume = """
张三，28岁，本科学历，5年工作经验
负责学员管理工作，组织培训活动，沟通协调各方资源
完成项目目标，提升团队效率，优化工作流程
具备良好的沟通能力和团队协作精神
"""

# 测试JD
test_jd = "招聘班主任岗位，要求具备学员管理、培训组织、沟通协调能力"

# 测试岗位
test_job_title = "班主任"

print("=" * 60)
print("Ultra引擎调试测试")
print("=" * 60)

try:
    print("\n1. 创建Ultra引擎实例...")
    engine = UltraScoringEngine(test_job_title, test_jd)
    print("   [OK] 引擎创建成功")
    
    print("\n2. 执行评分...")
    result = engine.score(test_resume)
    print("   [OK] 评分完成")
    
    print("\n3. 检查结果字段...")
    print(f"   - 总分: {result.get('总分', 'N/A')}")
    print(f"   - ai_review存在: {bool(result.get('ai_review'))}")
    print(f"   - highlight_tags数量: {len(result.get('highlight_tags', []))}")
    print(f"   - evidence_chains数量: {len(result.get('evidence_chains', {}))}")
    print(f"   - detected_actions_count: {result.get('detected_actions_count', 0)}")
    print(f"   - evidence_count: {result.get('evidence_count', 0)}")
    
    print("\n4. 详细字段检查...")
    if result.get('ai_review'):
        print(f"   [OK] ai_review: {result.get('ai_review')[:100]}...")
    else:
        print("   [FAIL] ai_review: 为空")
    
    if result.get('highlight_tags'):
        print(f"   [OK] highlight_tags: {result.get('highlight_tags')}")
    else:
        print("   [FAIL] highlight_tags: 为空")
    
    if result.get('evidence_chains'):
        print(f"   [OK] evidence_chains: {len(result.get('evidence_chains', {}))}个维度")
        for dim, evs in result.get('evidence_chains', {}).items():
            print(f"     - {dim}: {len(evs)}条证据")
    else:
        print("   [FAIL] evidence_chains: 为空")
    
    print("\n5. 错误检查...")
    if result.get('error_code'):
        print(f"   [WARN] error_code: {result.get('error_code')}")
        print(f"   [WARN] error_message: {result.get('error_message')}")
    else:
        print("   [OK] 无错误")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
except Exception as e:
    import traceback
    print(f"\n[ERROR] 测试失败: {str(e)}")
    print(f"异常堆栈:\n{traceback.format_exc()}")

