"""Deterministic command line entry points for people and coding agents."""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any


def _load_repo_env() -> None:
    try:
        from dotenv import load_dotenv

        candidate = Path.cwd() / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
    except Exception:
        pass


def _emit(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(payload.get("message") or payload.get("status") or "")
    for check in payload.get("checks") or []:
        marker = "OK" if check.get("ok") else "!!"
        print(f"[{marker}] {check.get('name')}: {check.get('message')}")
    action = payload.get("nextAction")
    if action:
        print(f"Next: {action.get('message')}")
        if action.get("command"):
            print(f"  {action['command']}")


def _build_with_reserved_stdout(builder, *, as_json: bool) -> dict[str, Any]:
    """Keep machine-readable stdout clean while importing application modules."""
    if not as_json:
        return builder()
    protocol_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        return builder()
    finally:
        sys.stdout = protocol_stdout


def _archive_accounts() -> list[dict[str, Any]]:
    try:
        from . import static_archive_store

        return static_archive_store.list_accounts()
    except Exception:
        return []


def _live_accounts() -> list[str]:
    try:
        from .chat_helpers import _list_decrypted_accounts

        return list(_list_decrypted_accounts())
    except Exception:
        return []


def build_status() -> dict[str, Any]:
    from . import __version__
    from .app_paths import get_output_dir

    live_accounts = _live_accounts()
    archive_accounts = _archive_accounts()
    archive_names = [str(item.get("account") or "") for item in archive_accounts if item.get("account")]
    ready = bool(live_accounts or archive_names)
    if ready:
        next_action = {
            "code": "ask_agent",
            "message": "Data is ready. Ask the agent to search, summarize, or analyze your WeChat history.",
        }
    else:
        next_action = {
            "code": "prepare_data",
            "message": "Start the local app, log in to WeChat, and complete the guided data preparation once.",
            "command": "uv run wechat-archive start",
        }
    return {
        "status": "ready" if ready else "needs_user_action",
        "version": __version__,
        "liveReady": bool(live_accounts),
        "archiveReady": bool(archive_names),
        "liveAccounts": live_accounts,
        "archiveAccounts": archive_accounts,
        "outputDir": str(get_output_dir()),
        "nextAction": next_action,
    }


def build_doctor() -> dict[str, Any]:
    from .app_paths import get_output_dir

    output_dir = get_output_dir()
    parent = output_dir
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    checks = [
        {
            "name": "python",
            "ok": sys.version_info >= (3, 11),
            "message": f"Python {platform.python_version()} (requires 3.11+)",
        },
        {
            "name": "platform",
            "ok": sys.platform in {"win32", "darwin"},
            "message": f"{platform.system()} {platform.release()} (data preparation supports Windows/macOS)",
        },
        {
            "name": "uv",
            "ok": bool(shutil.which("uv")),
            "message": "uv is available" if shutil.which("uv") else "Install uv before bootstrapping the repository",
        },
        {
            "name": "output",
            "ok": parent.exists() and os.access(parent, os.W_OK),
            "message": f"Runtime data directory: {output_dir}",
        },
    ]
    status = build_status()
    blocking = [check for check in checks if not check["ok"]]
    if blocking:
        state = "error"
    else:
        state = status["status"]
    return {
        "status": state,
        "ok": not blocking,
        "checks": checks,
        "data": status,
        "nextAction": status["nextAction"] if not blocking else {
            "code": "fix_environment",
            "message": "Fix the failed checks, then rerun `uv run wechat-archive doctor --json`.",
        },
    }


def bootstrap(*, as_json: bool) -> int:
    from .app_paths import get_output_dir

    get_output_dir().mkdir(parents=True, exist_ok=True)
    payload = _build_with_reserved_stdout(build_doctor, as_json=as_json)
    payload["bootstrapped"] = True
    _emit(payload, as_json=as_json)
    return 1 if payload["status"] == "error" else 0


def serve() -> None:
    _load_repo_env()
    multiprocessing.freeze_support()

    import uvicorn

    from .desktop_parent_watchdog import start_desktop_parent_watchdog_from_env
    from .native_core_client import configure_native_core_entrypoint
    from .runtime_settings import read_effective_backend_host, read_effective_backend_port

    start_desktop_parent_watchdog_from_env()
    configure_native_core_entrypoint()
    host, _ = read_effective_backend_host(default="127.0.0.1")
    port, _ = read_effective_backend_port(default=10392)
    uvicorn.run("wechat_decrypt_tool.api:app", host=host, port=port, log_level="info")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wechat-archive", description="Agent-ready WeChatDataAnalysis control plane")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "status", "bootstrap", "prepare"):
        child = subparsers.add_parser(name)
        child.add_argument("--json", action="store_true", dest="as_json")
    subparsers.add_parser("start")
    mcp = subparsers.add_parser("mcp")
    mcp.add_subparsers(dest="transport", required=True).add_parser("stdio")
    return parser


def main(argv: list[str] | None = None) -> int:
    _load_repo_env()
    args = _parser().parse_args(argv)
    if args.command == "doctor":
        payload = _build_with_reserved_stdout(build_doctor, as_json=args.as_json)
        _emit(payload, as_json=args.as_json)
        return 1 if payload["status"] == "error" else 0
    if args.command in {"status", "prepare"}:
        payload = _build_with_reserved_stdout(build_status, as_json=args.as_json)
        _emit(payload, as_json=args.as_json)
        return 0
    if args.command == "bootstrap":
        return bootstrap(as_json=args.as_json)
    if args.command == "start":
        serve()
        return 0
    if args.command == "mcp" and args.transport == "stdio":
        from .mcp.stdio import main as stdio_main

        stdio_main()
        return 0
    return 2


def serve_main() -> None:
    serve()


if __name__ == "__main__":
    raise SystemExit(main())
