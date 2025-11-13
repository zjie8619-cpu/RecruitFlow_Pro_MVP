# AI 生成失败故障排查指南

## 快速诊断

如果看到错误：`RetryError` 或 `AI 生成失败`，请按以下步骤排查：

### 1. 检查 .env 文件

**位置**：项目根目录（和 `requirements.txt` 同级）

**内容示例**：
```
SILICONFLOW_API_KEY=sk-xxxxxxxxxxxxxxxx
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
AI_MODEL=gpt-4o-mini
AI_TEMPERATURE=0.7
```

**注意事项**：
- 文件名必须是 `.env`（不是 `env.txt` 或 `.env.txt`）
- Key 值中不能有空格或中文标点
- 等号前后可以有空格，但建议不要

### 2. 重启 Streamlit

修改 `.env` 后必须重启才能生效：

```bash
# 先 Ctrl + C 停止
streamlit run app/streamlit_app.py
```

### 3. 使用诊断面板

在页面底部找到 **"🔧 AI 连接诊断"**，点击展开：

- 查看 **"已检测到 Key"** 是否为 ✅
- 查看 **Base URL** 和 **当前模型** 是否正确
- 点击 **"🧪 测试一次 AI 连通性"** 按钮

### 4. 常见错误及解决方案

#### ❌ "AI Key 未配置"
- **原因**：.env 文件不存在或 Key 未设置
- **解决**：创建/检查 .env 文件，确保在项目根目录

#### ❌ "401" 或 "403" 错误
- **原因**：API Key 无效或已过期
- **解决**：检查 .env 中的 Key 是否正确，去硅基流动控制台确认

#### ❌ "404" 错误
- **原因**：模型不存在或账号未开通
- **解决**：更换模型，如 `Qwen2.5-32B-Instruct` 或 `Qwen2.5-72B-Instruct`

#### ❌ 网络超时
- **原因**：公司网络拦截或连接不稳定
- **解决**：检查网络是否放行 `api.siliconflow.cn`，或尝试使用 OpenAI

### 5. 模型推荐

如果 `gpt-4o-mini` 不可用，尝试以下模型：

```
AI_MODEL=Qwen2.5-32B-Instruct
# 或
AI_MODEL=Qwen2.5-72B-Instruct
# 或
AI_MODEL=GLM-4-Plus
```

### 6. 极简修复清单

✅ .env 在项目根目录  
✅ 包含 `SILICONFLOW_API_KEY=你的key`  
✅ 包含 `AI_MODEL=可用模型名`  
✅ 已重启 Streamlit  
✅ 诊断面板测试通过  

如果以上都完成仍失败，请查看诊断面板的具体错误信息，按提示修复。

