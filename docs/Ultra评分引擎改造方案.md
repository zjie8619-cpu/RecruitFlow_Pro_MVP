# Ultra 评分引擎改造方案

## 一、新文件清单

### 1. 核心模块
- ✅ `backend/services/scoring_graph.py` - 标准化推理框架（S1-S9）
- ✅ `backend/services/ability_pool.py` - 能力池映射
- ✅ `backend/services/robust_parser.py` - 异常处理
- ✅ `backend/services/field_generators.py` - 四个字段生成器（Ultra版）
- ✅ `backend/services/ultra_scoring_engine.py` - Ultra评分引擎整合

### 2. 需要修改的文件
- `backend/services/ai_matcher.py` - 集成Ultra引擎
- `app/streamlit_app.py` - UI改造为折叠/展开式卡片

### 3. 测试文件
- `tests/test_scoring.py` - 单元测试

---

## 二、集成步骤

### Step 1: 修改 ai_matcher.py

在 `ai_score_one` 函数中添加 Ultra 引擎选项：

```python
from backend.services.ultra_scoring_engine import UltraScoringEngine

def ai_score_one_ultra(jd_text: str, resume_text: str, job_title: str = "") -> Dict[str, Any]:
    """Ultra版评分（使用新的推理框架）"""
    try:
        engine = UltraScoringEngine(job_title, jd_text)
        result = engine.score(resume_text)
        return result
    except Exception as e:
        # 回退到旧版本
        return ai_score_one(None, None, jd_text, resume_text, job_title)
```

### Step 2: 修改 streamlit_app.py

在显示候选人详情的地方，改为折叠/展开式卡片：

```python
# 按总分排序
result_df_sorted = result_df.sort_values(by="总分", ascending=False)

for idx, (_, row) in enumerate(result_df_sorted.iterrows()):
    candidate_name = row.get('name', '匿名候选人')
    score_value = float(row.get("总分", 0))
    
    # 折叠式卡片
    with st.expander(f"👤 {candidate_name} | 总分：{score_value:.1f}", expanded=False):
        # 显示所有内容
        ...
```

---

## 三、最终JSON示例

见 `docs/ultra_output_example.json`

---

## 四、单元测试

见 `tests/test_scoring.py`

