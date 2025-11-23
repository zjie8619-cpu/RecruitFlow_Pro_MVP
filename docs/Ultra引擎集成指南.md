# Ultra 评分引擎集成指南

## 一、已创建的新文件

### 核心模块（已完成）
1. ✅ `backend/services/scoring_graph.py` - 标准化推理框架（S1-S9）
2. ✅ `backend/services/ability_pool.py` - 12类能力池映射
3. ✅ `backend/services/robust_parser.py` - 异常处理模块
4. ✅ `backend/services/field_generators.py` - 四个字段生成器（Ultra版）
5. ✅ `backend/services/ultra_scoring_engine.py` - Ultra评分引擎整合
6. ✅ `backend/services/ai_matcher_ultra.py` - Ultra版匹配器

### 测试和文档（已完成）
7. ✅ `tests/test_scoring.py` - 单元测试
8. ✅ `docs/ultra_output_example.json` - 最终JSON示例

---

## 二、需要修改的文件

### 1. 修改 `app/streamlit_app.py`

在文件开头添加导入：

```python
# 在现有导入后添加
from backend.services.ai_matcher_ultra import ai_match_resumes_df_ultra
```

在 `ai_match_resumes_df` 调用处替换为Ultra版本：

**找到这一行（约1001行）：**
```python
scored_df = ai_match_resumes_df(jd_text, resumes_df, job_title)
```

**替换为：**
```python
# 使用Ultra版评分引擎
try:
    scored_df = ai_match_resumes_df_ultra(jd_text, resumes_df, job_title)
except Exception as e:
    st.warning(f"Ultra引擎失败，回退到标准版本: {e}")
    scored_df = ai_match_resumes_df(jd_text, resumes_df, job_title)
```

**在候选人详情展示部分（约1057行），确保按总分排序：**

```python
# 按总分排序（高分在前）
result_df_sorted = result_df.sort_values(by="总分", ascending=False).reset_index(drop=True)

st.markdown("### 候选人洞察详情")
for idx, (_, row) in enumerate(result_df_sorted.iterrows()):
    candidate_name = row.get('name', '匿名候选人')
    score_label = row.get("总分")
    score_value = float(score_label) if score_label is not None else 0
    
    # 折叠式卡片（默认折叠）
    expander_title = f"👤 {candidate_name} ｜ 总分：{score_value:.1f}"
    with st.expander(expander_title, expanded=False):
        # ... 现有内容保持不变
```

**添加AI评价字段显示（在现有内容中添加）：**

```python
# 在简历摘要后添加
ai_review = row.get("ai_review", "")
if ai_review:
    st.markdown("**🤖 AI 评价**")
    st.markdown(f'<div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff;">{ai_review}</div>', unsafe_allow_html=True)
```

---

## 三、字段映射说明

Ultra引擎输出的字段与现有字段的映射关系：

| Ultra字段 | 现有字段 | 说明 |
|-----------|----------|------|
| `ai_review` | `short_eval` | AI评价（Ultra版，更详细） |
| `highlight_tags` | `highlights` | 亮点标签（列表格式） |
| `ai_resume_summary` | `resume_mini` | 简历摘要（Ultra版） |
| `evidence_text` | `证据` | 证据文本（结构化） |
| `risks` | - | 风险列表（新增） |
| `match_level` | - | 匹配度等级（新增） |

---

## 四、测试步骤

1. **运行单元测试**：
```bash
python -m pytest tests/test_scoring.py -v
```

2. **在Streamlit中测试**：
   - 启动应用
   - 上传简历
   - 运行AI匹配
   - 检查是否显示Ultra字段

3. **验证输出**：
   - 检查 `ai_review` 是否包含【证据】【推理】【结论】三段
   - 检查 `highlight_tags` 是否为2-5个标签
   - 检查 `evidence_text` 是否按维度分组
   - 检查卡片是否按总分排序

---

## 五、回退方案

如果Ultra引擎出现问题，系统会自动回退到标准版本：

```python
try:
    scored_df = ai_match_resumes_df_ultra(jd_text, resumes_df, job_title)
except Exception as e:
    # 自动回退
    scored_df = ai_match_resumes_df(jd_text, resumes_df, job_title)
```

---

## 六、性能优化建议

1. **缓存能力池映射**：避免重复计算
2. **批量处理优化**：对大量简历使用并行处理
3. **错误重试机制**：对临时错误进行重试

---

## 七、后续优化方向

1. 支持更多岗位类型的能力池
2. 优化动作识别准确率
3. 增强风险识别能力
4. 支持自定义权重矩阵

