# Runtime workflows

## First-run state machine

Run:

```text
uv run --frozen wechat-archive doctor --json
```

- `ready`: use MCP immediately. The web backend does not need to be running for
  STDIO MCP.
- `needs_user_action` + `prepare_data`: run `wechat-archive prepare --json`, then
  start the local app. Ask the user to log in to WeChat and complete the guided
  preparation. Resume with `doctor --json` after they confirm.
- `error`: fix only the failed `checks`; rerun doctor afterward.

Do not ask the user for a database key. The local app owns discovery, validation,
and storage of credentials.

## Analysis workflow

1. Check `wechat.core.get_status`.
2. Resolve the account and target conversation/person.
3. Prefer static tools when `archiveReady` is true and the request concerns a
   saved snapshot. Static data remains usable even when `liveReady` is false.
4. Read a small page first. Expand by time range or pagination only as needed.
5. Record the source, time coverage, and any gaps in the final answer.

## Common intents

- “总结这个群最近的讨论”: resolve group, read a bounded recent range, summarize.
- “在历史里找某件事”: search first, then fetch context around relevant hits.
- “比较两个人/两个群”: use the same time window and comparable limits.
- “做知识库”: use the static archive, process chronologically in bounded pages,
  and save only a user-approved derived artifact.
- “为什么找不到”: inspect readiness and source freshness; do not invent data.

## MCP recovery

If project MCP tools are not visible:

1. Confirm the repository is trusted in the client.
2. Run `uv run --frozen wechat-archive mcp stdio` only as a diagnostic; it waits
   for JSON-RPC on stdin, so stop it after confirming it starts.
3. Restart the client so it reloads `.codex/config.toml` or `.mcp.json`.
