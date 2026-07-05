@echo off
chcp 65001 >nul
title WeChat 静态归档 - 启动器
cd /d "%~dp0"

echo ============================================================
echo   WeChat 静态归档 - 开发环境
echo   后端(热更新) + 前端，配置(含 API Key)从 .env 读取
echo ============================================================
echo.

echo [1/2] 启动后端（dev_watch 热更新，改后端代码自动重启）...
start "WeChat 后端(热更新)" cmd /k "uv run dev_watch.py"

echo [2/2] 启动前端（Nuxt，改前端代码自动刷新）...
start "WeChat 前端" cmd /k "npm --prefix frontend run dev"

echo.
echo 正在等待服务就绪，随后自动打开浏览器（约 12 秒）...
timeout /t 12 >nul
start "" http://localhost:3000/static-chat

echo.
echo 已启动。新弹出的两个窗口分别是「后端」和「前端」，
echo 想停止服务时关闭那两个窗口即可。本窗口可直接关闭。
timeout /t 4 >nul
