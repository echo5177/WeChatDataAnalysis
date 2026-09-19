# WeChatDataAnalysis Agent Guide

This repository is an agent-ready, privacy-sensitive fork of
`LifeArchiveProject/WeChatDataAnalysis`. Treat chat history, account identifiers,
database keys, media, logs, and generated reports as private local data.

## When the user asks about their WeChat data

1. Use the repository skill `wechat-data-operator`.
2. Run `uv run --frozen wechat-archive doctor --json` before guessing about setup.
3. If the result is `ready`, use the project MCP server. Prefer `wechat.static.*`
   for archived/reproducible analysis and `wechat.chat.*` for current data.
4. If the result is `needs_user_action`, run
   `uv run --frozen wechat-archive prepare --json`, explain only the returned
   action, and start the local app with `uv run --frozen wechat-archive start`
   when preparation is required. The user may need to log in to WeChat and
   approve access to data they own; do not ask them to find or paste a key.
5. Keep reads bounded and paginate. Give the answer, not a dump of raw history.

The checked-in `.codex/config.toml` and `.mcp.json` launch the same local STDIO
MCP server. STDIO needs neither an HTTP endpoint nor a bearer token. Never print
or copy database keys, image keys, MCP tokens, or third-party API keys.

## Safety and privacy

- Operate only on data the user owns or is authorized to process.
- Default to read-only analysis. The public MCP catalog is intentionally read-only.
- Do not upload chat content, databases, media, logs, or identifiers to external
  services unless the user explicitly requests that exact transfer and understands it.
- Store runtime data only under the configured data/output directory. Never add
  `.env`, databases, logs, account stores, exported chats, or real-data fixtures to Git.
- Tests must use generated data and temporary directories.
- If a request would edit WeChat data, send messages, manage contacts/groups, or
  delete data, stop and get explicit confirmation; those actions are outside the
  public MCP surface.

## Repository workflow

- Python 3.11+ and `uv` are required. Use `uv sync --frozen --group dev`.
- Frontend: `cd frontend`, `npm ci`, then `npm test` or `npm run build`.
- Focused backend validation:
  `uv run --frozen pytest tests/test_mcp_router.py tests/test_mcp_stdio.py tests/test_static_archive_mcp.py tests/test_agent_ready_cli.py -q`.
- Run `uv run --frozen python tools/audit_public_repo.py` before a public push.
- Preserve the `upstream` remote and upstream attribution. Keep changes in small,
  reviewable commits and never rewrite upstream history.
