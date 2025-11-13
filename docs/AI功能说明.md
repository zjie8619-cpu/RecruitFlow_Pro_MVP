# AI智能生成功能说明

## 功能概述

RecruitFlow 现已支持AI智能生成JD和评分规则！只需输入岗位名称，AI就能自动生成专业的岗位描述、任职要求和评分维度。

## 支持的AI提供商

- **硅基流动 (SiliconFlow)**：✅ 已配置，支持 DeepSeek、Qwen 等模型（推荐）
- **OpenAI**：支持 GPT-4、GPT-4o-mini 等模型
- **Claude**：支持 Claude 3.5 Sonnet 等模型
- **离线模式**：无需API，使用预设规则

## 快速开始

### 1. 安装AI依赖（可选）

如果使用AI功能，需要安装对应的SDK：

```bash
# 硅基流动、OpenAI（使用openai SDK）
pip install openai>=1.0.0

# Claude
pip install anthropic>=0.18.0
```

### 2. 设置API密钥

**硅基流动（推荐，已预配置）：**
- API密钥已写入 `backend/configs/api_keys.json`
- 默认使用 `deepseek-chat` 模型
- 无需额外配置，直接可用！

**OpenAI：**
```bash
# 方式1：环境变量
# Windows PowerShell
$env:OPENAI_API_KEY="your-api-key-here"

# Linux/Mac
export OPENAI_API_KEY="your-api-key-here"

# 方式2：配置文件
# 编辑 backend/configs/api_keys.json，添加 "openai_api_key"
```

**Claude：**
```bash
# 方式1：环境变量
# Windows PowerShell
$env:ANTHROPIC_API_KEY="your-api-key-here"

# Linux/Mac
export ANTHROPIC_API_KEY="your-api-key-here"

# 方式2：配置文件
# 编辑 backend/configs/api_keys.json，添加 "anthropic_api_key"
```

### 3. 在Web界面配置

1. 打开侧边栏的"设置"
2. 在"AI配置"中选择提供商：
   - **siliconflow**（推荐，已配置好）
   - openai
   - claude
   - offline（离线模式）
3. （可选）输入模型名称：
   - 硅基流动：`deepseek-chat`、`Qwen/Qwen2.5-72B-Instruct` 等
   - OpenAI：`gpt-4o-mini`、`gpt-4` 等
   - Claude：`claude-3-5-sonnet-20241022` 等
4. 点击"保存设置"

### 4. 使用AI生成

1. 在"步骤 0"中，勾选"输入新岗位名称（AI智能生成）"
2. 输入任意岗位名称，如"数据分析师"、"产品经理"等
3. 在"步骤 1"中，点击"🤖 使用AI智能生成"按钮
4. 等待AI生成完成（通常10-30秒）
5. 查看生成的JD和评分规则，可编辑后保存

## 功能特点

- ✅ **智能理解**：AI会根据岗位名称理解岗位特点
- ✅ **专业生成**：生成符合行业标准的JD和评分维度
- ✅ **自动回退**：AI失败时自动使用离线规则
- ✅ **灵活配置**：支持自定义模型和参数

## 注意事项

1. **API费用**：使用AI功能会产生API调用费用，请关注使用量
2. **网络要求**：
   - 硅基流动：需要访问 `api.siliconflow.cn`
   - OpenAI：需要访问 `api.openai.com`
   - Claude：需要访问 `api.anthropic.com`
3. **生成质量**：建议生成后人工审核和调整
4. **离线优先**：未配置API时自动使用离线模式，不影响其他功能
5. **API密钥安全**：`backend/configs/api_keys.json` 已加入 `.gitignore`，不会被提交到代码仓库

## 字段汉化说明

所有显示字段已汉化：
- `skill_fit` → 技能贴合度
- `exp_relevance` → 经验相关性
- `stability` → 稳定性
- `growth` → 成长性
- `confidence` → 置信度
- `blocked_by_threshold` → 阈值拦截
- `evidence` → 证据链

数据库字段保持英文（兼容性），仅在UI显示时汉化。

