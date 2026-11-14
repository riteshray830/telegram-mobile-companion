@echo off
title Friday Auto-Start Status
echo ========================================================
echo   ⚙️ Friday Auto-Start & Service Status
echo ========================================================
echo.
python "%~dp0\telegram-companion-mcp\autostart_manager.py"
echo.
echo ========================================================
pause
