# Privacy and release boundaries

## Local by default

The source database, extracted keys, static archive, exports, logs, and media stay
on the user's machine. MCP responses should contain only the records required for
the current answer.

Do not place private data in prompts sent to a third-party model configured in the
web app unless the user explicitly chose that provider and requested the analysis.
Do not confuse the optional in-app `LLM_API_KEY` with Codex/Claude MCP access;
STDIO MCP needs no token.

## Never disclose or commit

- database/image keys, bearer tokens, API keys, cookies, or session material;
- `.env`, `account_keys.json`, `runtime_settings.json`, databases, WAL/SHM files;
- chat exports, media, logs, screenshots containing identities, or real wxids;
- generated summaries that reveal people beyond the user's stated task.

Use synthetic fixtures and temporary directories in tests. Run
`uv run --frozen python tools/audit_public_repo.py` before a public push.

## Explicit confirmation required

Get confirmation before external upload/sharing, bulk export, editing local WeChat
data, sending messages, contact/group actions, or deletion. The public MCP tools
are read-only; do not bypass that boundary through internal HTTP routes.
