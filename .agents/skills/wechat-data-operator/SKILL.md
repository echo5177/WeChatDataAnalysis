---
name: wechat-data-operator
description: Safely operate this repository to search, summarize, compare, or analyze the user's authorized local WeChat data through the bundled CLI and MCP server. Use when the user asks Codex or Claude Code to work with WeChat chats, contacts, Moments, media metadata, analytics, or the static archive. Do not use for unrelated repository development or for data the user is not authorized to access.
---

# WeChat Data Operator

Turn the user's natural-language request into bounded, read-only operations. The
user should not need to understand database keys, tokens, endpoints, or MCP.

## Start

1. Run `uv run --frozen wechat-archive doctor --json`.
2. Follow `status` and `nextAction` exactly.
3. When status is `ready`, use the bundled `wechat-data-analysis` MCP tools.
4. When status is `needs_user_action`, read `references/workflows.md` and ask
   only for the human action that cannot be automated (normally logging in to
   WeChat or confirming access to owned data).

## Route the request

- Static archive, knowledge base, reproducible history: start with
  `wechat.static.list_conversations`; use `wechat.static.search_messages` or
  bounded `wechat.static.read_range` calls.
- Current chats: resolve a session, then use `wechat.chat.*` with small limits.
- Person or group is ambiguous: resolve before reading messages.
- Moments, media links, or aggregate statistics: select the matching MCP package;
  do not load the entire catalog unless discovery is necessary.
- Empty or stale results: check `wechat.core.get_status` and report the precise
  preparation action instead of guessing about keys.

Read `references/workflows.md` for detailed state transitions and
`references/privacy.md` whenever output, export, external AI, or sharing is involved.

## Answering rules

- Use the minimum data needed, paginate, and stop when the evidence is sufficient.
- Summarize rather than reproducing long conversations. Quote only short passages
  needed to support the answer.
- Distinguish live data from a static snapshot and state the covered time range.
- Never expose keys, tokens, local database paths, or unrelated personal identifiers.
- Do not send, edit, delete, export, or upload data without explicit user approval.
