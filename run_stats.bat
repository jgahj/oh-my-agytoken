@echo off
chcp 65001 >nul
title Antigravity Token 实时监控服务 (秒级监听同步)
cd /d "%~dp0"
echo ====================================================================
echo        Antigravity Token 实时监控服务 (秒级监听同步)
echo ====================================================================
echo 正在启动本地实时监控服务并唤起仪表盘...
echo [提示] 保持本窗口运行即可实现本地会话秒级实时监听与自动同步。
echo [提示] 按 Ctrl+C 可安全停止监控服务。
echo.

set PYTHONUTF8=1
py -3.14 -X utf8 export_report.py
if %errorlevel% neq 0 (
    python -X utf8 export_report.py
)

pause
