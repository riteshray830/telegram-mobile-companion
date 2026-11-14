@echo off
title Disable Friday Windows Auto-Start
echo ========================================================
echo   🛑 Disabling Friday Auto-Start on Boot...
echo ========================================================
echo.
python "%~dp0\telegram-companion-mcp\autostart_manager.py" disable
echo.
echo ========================================================
pause
