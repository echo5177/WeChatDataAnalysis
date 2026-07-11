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
echo 正在等待前端编译就绪（首次较慢，请耐心等待，会自动打开，无需手动刷新）...
rem 轮询并"预热"目标页面：Invoke-WebRequest 会触发 Nuxt/Vite 的按需编译，
rem 只有当页面真正编译好、返回 200 后才打开浏览器，避免黑屏/需手动刷新。
powershell -NoProfile -Command "$u='http://localhost:3000/static-chat'; for($i=0;$i -lt 180;$i++){ try{ $r=Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 5; if($r.StatusCode -eq 200){ Write-Host '  前端已就绪，正在打开浏览器...'; break } }catch{ Start-Sleep -Milliseconds 800 } }"
start "" http://localhost:3000/static-chat

echo.
echo 已启动。新弹出的两个窗口分别是「后端」和「前端」，
echo 想停止服务时关闭那两个窗口即可。本窗口可直接关闭。
timeout /t 4 >nul
