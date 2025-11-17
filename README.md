# Calliope CLI (Writing/拆书 Agent)

Calliope is a minimal writing/拆书命令行 Agent，支持聊天式 UI + RAG（索引/检索）+ 写作工具（大纲/摘要/润色）。

- 工具：文件读写、RAG 索引/检索、写作（Outline/Summarize/Rewrite），可选子 Agent、内部待办
- 配置：`~/.calliope/config.json` （自动创建）

## 快速开始
```bash
uv run calliope --help
```

示例（打印模式）：
```bash
uv run calliope --print --command "帮我为《示例书》生成拆书大纲"
```

### 配置 DeepSeek（示例）
在 `~/.calliope/config.json` 配置一个 provider：
```json
{
  "default_model": "deepseek-chat",
  "providers": {
    "deepseek": {
      "type": "deepseek",
      "base_url": "https://api.deepseek.com",  // OpenAI-compatible /v1/chat/completions
      "api_key": "dummy"
    }
  },
  "models": {
    "deepseek-chat": {
      "provider": "deepseek",
      "model": "deepseek-chat",
      "max_context_size": 100000
    }
  }
}
```
或者通过环境变量覆盖：`DEEPSEEK_BASE_URL`、`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL_NAME`、`DEEPSEEK_MODEL_MAX_CONTEXT_SIZE`。

## 结构
参考 `CALLIOPE_DESIGN.md` 获取模块与目录说明。当前代码包含若干占位（stub）实现，适用于后续扩展向量检索、子 Agent 流程等。
