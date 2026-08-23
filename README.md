# astrbot_plugin_vision_router

为纯文本 LLM 提供视觉能力的 AstrBot 插件。灵感来自 DeepSeek Harness 生态的 `dsh-vision-router`。

> 当你的主模型不支持识图时，这个插件会"借用"一个可识图的视觉模型 API，把图片识别成文字描述，让纯文本模型也能"看到"图片内容。

## ✨ 功能

- 自动识别消息中的图片（支持 URL、本地文件、base64）
- 调用任意 **OpenAI 兼容**的视觉模型 API 识图
- 支持触发模式：`auto`（收到图片自动识别）/ `command`（指令触发）/ `both`（两者）
- 支持多图逐张识别、失败重试、超时控制
- 在 AstrBot 管理面板提供可视化配置表单

## 🖼️ 支持的视觉模型

只要是 OpenAI 兼容格式的视觉（Vision）模型都可以，例如：

| 模型 | API 地址 |
|------|----------|
| 阿里云百炼 Qwen-VL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 智谱 GLM-4V | `https://open.bigmodel.cn/api/paas/v4` |
| OpenAI GPT-4o | `https://api.openai.com/v1` |
| DeepSeek-V4-Flash-Vision | DeepSeek 兼容端 |
| 本地 Ollama 视觉模型 | `http://127.0.0.1:11434/v1` |

## 📦 安装

1. 下载本项目 zip，或 `git clone`。
2. 将插件目录放入 AstrBot 的 `plugins` 目录。
3. 在 AstrBot 管理面板 → 插件管理 → **重新加载插件**。

## ⚙️ 配置

在 AstrBot 管理面板的插件设置中填写：

- **api_key**：视觉模型 API Key（必填）
- **api_base**：视觉模型 API 地址（OpenAI 兼容）
- **model**：模型名（如 `qwen-vl-max`）
- **trigger_mode**：`auto` / `command` / `both`
- **command**：触发指令（默认 `/看图`）
- **prompt**：默认识图提示词
- **reply_prefix**：回复前缀（默认 `【识图】`）
- **timeout**：请求超时（秒）
- **max_retries**：失败重试次数
- **show_typing**：识图前发送"正在识图"提示

## 🚀 使用

```text
# 群里发图片，机器人自动识图
[图片]

# 或自定义提示词识图
/看图 这张图里有什么文字？
```

## 📄 License

MIT
