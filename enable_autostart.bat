@echo off
title Enable Friday Windows Auto-Start
echo ========================================================
echo   🚀 Enabling Friday Auto-Start on Boot...
echo ========================================================
echo.
python "%~dp0\telegram-companion-mcp\autostart_manager.py" enable
echo.
echo ========================================================
pause
