#!/usr/bin/env python3
"""开发用热更新：代码改动时自动重启整个后端进程。

为什么不用 uvicorn 自带的 --reload？
    uvicorn 的内置 reloader 会用子进程方式重新导入 app，而本项目的原生 WCDB
    引擎（wcdb_api.dll + InitProtection）在这种“进程内重导入”下会初始化失败、
    导致 worker 起不来。所以这里改用 watchfiles 的“整进程重启”：每次改动都是
    一次全新的 `main.py` 启动（等价于你手动重启），原生 DLL 每次干净加载，不冲突。

用法：
    uv run dev_watch.py
    （环境变量和 main.py 一致：WECHAT_TOOL_PORT / WECHAT_TOOL_DATA_DIR / LLM_API_KEY ...）

改完 src/ 或 main.py 里的后端代码保存后，后端会自动重启，无需手动杀进程。
前端有自己的 HMR，不受此影响。
"""

from pathlib import Path

from watchfiles import PythonFilter, run_process

ROOT = Path(__file__).resolve().parent


def _run_backend() -> None:
    """Run main.py as __main__ in this (fresh) worker process."""
    import runpy

    runpy.run_path(str(ROOT / "main.py"), run_name="__main__")


def main() -> None:
    # Function target: watchfiles spawns a fresh Python worker to run the backend
    # and restarts that whole worker on .py changes. Because it's a full new
    # process each time, the native WCDB engine initialises cleanly (unlike
    # uvicorn's in-process --reload). Avoids Windows shlex/quoting pitfalls too.
    print("[dev_watch] 监听 src/ 与 main.py，改代码保存后自动重启后端（Ctrl+C 退出）")
    run_process(
        ROOT / "src",
        ROOT / "main.py",
        target=_run_backend,
        target_type="function",
        watch_filter=PythonFilter(),
    )


if __name__ == "__main__":
    main()
