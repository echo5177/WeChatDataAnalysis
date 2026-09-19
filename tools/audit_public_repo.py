#!/usr/bin/env python3
"""Fail when the current Git tree contains high-confidence private artifacts.

This is a release guard, not a replacement for reviewing commit history with a
dedicated secret scanner before publishing an existing private repository.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_NAMES = {
    ".env",
    "account_keys.json",
    "runtime_settings.json",
    "static_archive.db",
}
FORBIDDEN_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".pem",
    ".p12",
    ".pfx",
    ".har",
    ".pcap",
}
SKIP_CONTENT_SUFFIXES = {
    ".gif",
    ".ico",
    ".jpg",
    ".jpeg",
    ".png",
    ".ttf",
    ".wasm",
    ".whl",
    ".woff2",
    ".zip",
}
SECRET_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openai-key": re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    "github-token": re.compile(r"\b(?:gh[oprsu]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b"),
    "aws-access-key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def audit() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT).as_posix()
        name = path.name.lower()
        suffix = path.suffix.lower()
        if name in FORBIDDEN_NAMES or suffix in FORBIDDEN_SUFFIXES or name.endswith(("-wal", "-shm")):
            findings.append({"kind": "private-artifact", "path": relative})
            continue
        if suffix in SKIP_CONTENT_SUFFIXES or not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for kind, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append({"kind": kind, "path": relative})
    return findings


def validate_agent_configs() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    try:
        codex = tomllib.loads((ROOT / ".codex" / "config.toml").read_text(encoding="utf-8"))
        server = codex["mcp_servers"]["wechat_data_analysis"]
        if server.get("command") != "uv" or "stdio" not in server.get("args", []):
            raise ValueError("unexpected Codex MCP command")
    except Exception as exc:
        findings.append({"kind": "invalid-codex-config", "path": f".codex/config.toml: {exc}"})
    try:
        claude = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = claude["mcpServers"]["wechat-data-analysis"]
        if server.get("command") != "uv" or "stdio" not in server.get("args", []):
            raise ValueError("unexpected Claude MCP command")
    except Exception as exc:
        findings.append({"kind": "invalid-claude-config", "path": f".mcp.json: {exc}"})
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    findings = audit() + validate_agent_configs()
    payload = {"status": "fail" if findings else "pass", "findings": findings}
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif findings:
        print("Public-tree audit failed:")
        for item in findings:
            print(f"- {item['kind']}: {item['path']}")
    else:
        print("Public-tree audit passed: no tracked private artifacts or high-confidence secrets found.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
