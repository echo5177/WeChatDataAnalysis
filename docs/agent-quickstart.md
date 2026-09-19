# Agent 快速开始

目标：clone 后把仓库交给 Codex 或 Claude Code，用户用自然语言描述任务，不需要手工处理密钥、
HTTP endpoint 或 MCP token。

## 一分钟开始

```bash
git clone https://github.com/echo5177/WeChatDataAnalysis.git
cd WeChatDataAnalysis
codex
```

Codex 首次信任项目后会读取：

- `AGENTS.md`：安全边界、启动和验证规则；
- `.agents/skills/wechat-data-operator/`：本地微信数据任务的标准工作流；
- `.codex/config.toml`：自动启动 `wechat-data-analysis` STDIO MCP；
- `uv.lock`：可复现的 Python 依赖。

Claude Code 使用相同的 `AGENTS.md`（由 `CLAUDE.md` 引入）和 `.mcp.json`。

## Agent 的状态流程

Agent 首先执行：

```bash
uv run --frozen wechat-archive doctor --json
```

结果只有三类：

| 状态 | 含义 | 后续 |
| --- | --- | --- |
| `ready` | 实时数据或静态归档至少一种可用 | 直接调用 MCP 完成任务 |
| `needs_user_action` | 环境正常，但还没有可读数据 | 启动本地应用，请用户登录并完成一次引导 |
| `error` | Python、平台、uv 或目录权限异常 | 只修复返回的失败检查 |

首次准备数据时，人需要完成登录和授权确认。数据库密钥的发现、验证和本地保存由应用负责；
Agent 不应要求用户粘贴密钥。

## 两种数据源

- `wechat.chat.*`：当前/实时数据，适合“最近发生了什么”。
- `wechat.static.*`：用户主动保存的冻结快照，适合长期知识库、可复现总结和跨群人物分析。

静态归档与解密目录解耦；即使实时数据库暂不可用，archive-only 状态也可被 MCP 自动发现。

## 隐私

默认只读、默认本机。STDIO MCP 不监听端口、不使用 token。仓库已忽略 `.env`、数据库、密钥存储、
日志和导出文件。外部上传、批量导出、写入微信数据、发送消息或删除操作都必须由用户明确授权，
且不属于公开 MCP 工具范围。

发布前运行：

```bash
uv run --frozen python tools/audit_public_repo.py
```
