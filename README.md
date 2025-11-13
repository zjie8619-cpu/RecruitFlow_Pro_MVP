# RecruitFlow（教育机构版）— 一键招聘流水线 · Pro MVP

**目标**：把"写 JD → 批量筛简历 → 排面试 → 发邀约 → 面后出结论 → 导出报表"做成一个按钮，适配线上教育岗位（课程顾问/教学运营/教研编辑等）。

- 离线可跑：Windows/Mac 本地运行（Python 3.10+）。
- 可检视代码：结构清晰、带单测、可回滚快照。
- 风控齐全：盲筛、人审闸、置信度阈值、版本快照、审计、脱敏导出。
- 数据沉淀：SQLite 本地库 + CSV/Excel 导出（Excel 依赖缺失时自动降级，仅导出 CSV）。

## 快速开始
```bash
pip install -r requirements.txt
python scripts/seed_data.py
python scripts/run_round.py --job 课程顾问 --topn 10
# 可选：streamlit run app/streamlit_app.py
```

接入 Claude/OpenAI：见 docs/开发说明.md，切换 backend/configs/model_config.json 的 llm_provider 并设置 API Key。

