"""Newline-delimited MCP stdio transport.

Stdout is reserved for JSON-RPC responses.  Application diagnostics are sent
to stderr so Codex, Claude Code, and other MCP clients can launch this server
without an HTTP endpoint or bearer token.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, BinaryIO


class _StdioRequest:
    @property
    def base_url(self) -> str:
        return ""


async def serve_stdio(stdin: BinaryIO, stdout: BinaryIO) -> None:
    from .protocol import handle_jsonrpc_payload, parse_error_response
    from .registry import McpToolContext
    from .tools import MCP_REGISTRY

    context = McpToolContext(request=_StdioRequest())
    while True:
        line = await asyncio.to_thread(stdin.readline)
        if not line:
            return
        if not line.strip():
            continue

        try:
            payload: Any = json.loads(line.decode("utf-8-sig"))
        except Exception:
            response = parse_error_response()
        else:
            response = await handle_jsonrpc_payload(payload, MCP_REGISTRY, context)

        if response is None:
            continue
        encoded = json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        stdout.write(encoded + b"\n")
        stdout.flush()


def main() -> None:
    protocol_stdout = sys.stdout.buffer
    # Anything imported by the tool registry that prints must not corrupt the
    # MCP wire stream.
    sys.stdout = sys.stderr
    asyncio.run(serve_stdio(sys.stdin.buffer, protocol_stdout))


if __name__ == "__main__":
    main()
