"""
测试日志输出是否正常
"""
import sys
import os
sys.path.insert(0, '.')

# 强制刷新输出
sys.stdout.flush()
sys.stderr.flush()

print("=" * 60)
print("测试日志输出")
print("=" * 60)
print("[DEBUG] 这是一条测试日志")
print("[DEBUG] 如果你能看到这条消息，说明日志输出正常")
print("=" * 60)

# 测试导入Ultra引擎
try:
    from backend.services.ultra_scoring_engine import UltraScoringEngine
    print("[DEBUG] Ultra引擎导入成功")
    
    # 测试创建引擎实例
    engine = UltraScoringEngine("测试岗位", "测试JD")
    print("[DEBUG] Ultra引擎实例创建成功")
    
    # 测试简单评分
    test_resume = "张三，28岁，负责学员管理工作，组织培训活动"
    print(f"[DEBUG] 开始测试评分，简历长度={len(test_resume)}")
    result = engine.score(test_resume)
    print(f"[DEBUG] 评分完成，总分={result.get('总分', 0)}")
    print(f"[DEBUG] ai_review存在: {bool(result.get('ai_review'))}")
    print(f"[DEBUG] highlight_tags数量: {len(result.get('highlight_tags', []))}")
    print(f"[DEBUG] evidence_chains数量: {len(result.get('evidence_chains', {}))}")
    
    print("=" * 60)
    print("测试完成 - 所有日志应该都能正常显示")
    print("=" * 60)
    
except Exception as e:
    import traceback
    print(f"[ERROR] 测试失败: {str(e)}")
    print(f"[ERROR] 异常堆栈:\n{traceback.format_exc()}")

