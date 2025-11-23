# Ultra引擎文件结构图

## 核心文件清单

### 1. 后端核心文件
```
backend/services/
├── ultra_scoring_engine.py      # Ultra评分引擎主入口
├── scoring_graph.py             # S1-S9标准化推理框架
├── field_generators.py          # 四个字段生成器（Ultra版）
├── ability_pool.py              # 12类能力池映射
├── robust_parser.py             # 异常处理模块
└── ai_matcher_ultra.py          # Ultra版批量匹配（DataFrame）
```

### 2. 前端文件
```
app/
└── streamlit_app.py             # Streamlit UI（2203行）
```

### 3. 参考文件
```
docs/
└── ultra_output_example.json    # Ultra-Format JSON示例
```

## Ultra-Format JSON结构（强制遵守）

```json
{
  "score_detail": {
    "skill_match": {"score": float, "evidence": [...]},
    "experience_match": {"score": float, "evidence": [...]},
    "growth_potential": {"score": float, "evidence": [...]},
    "stability": {"score": float, "evidence": [...]},
    "final_score": float
  },
  "persona_tags": [str],  // 或 highlight_tags
  "strengths_reasoning_chain": {
    "conclusion": str,
    "detected_actions": [str],
    "resume_evidence": [str],
    "ai_reasoning": str
  },
  "weaknesses_reasoning_chain": {
    "conclusion": str,
    "resume_gap": [str],
    "compare_to_jd": str,
    "ai_reasoning": str
  },
  "resume_mini": str,
  "match_summary": str,
  "risks": [...]
}
```

## 数据流

```
简历文本
  ↓
RobustParser (S1: 文本清洗)
  ↓
ScoringGraph (S2-S9: 推理框架)
  ↓
FieldGenerators (生成四个字段)
  ↓
UltraScoringEngine (整合输出)
  ↓
ai_matcher_ultra (批量处理)
  ↓
streamlit_app (前端展示)
```

## 当前问题清单

1. ❌ `strengths_reasoning_chain` 和 `weaknesses_reasoning_chain` 未生成
2. ❌ `persona_tags` 字段名不一致（使用 `highlight_tags`）
3. ❌ AI评价排版混乱（换行、去重问题）
4. ❌ 优势/劣势推理链在前端为空
5. ❌ 雷达图ID冲突（需要更唯一的key）
6. ❌ 字段映射不一致（后端→前端）



