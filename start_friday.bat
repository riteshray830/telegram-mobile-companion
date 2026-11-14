@echo off
title Friday Remote Companion
echo ========================================================
echo   🚀 Starting Friday Remote Companion...
echo ========================================================
echo.
cd /d "%~dp0\telegram-companion-mcp"
python -u friday_runner.py
pause
