@echo off
title Setup Telegram Companion for Laptop
echo ========================================================
echo   📱 Friday Telegram Companion - Laptop Setup Wizard
echo ========================================================
echo.
cd /d "%~dp0\telegram-companion-mcp"
echo [1/3] Installing dependencies...
pip install -r requirements.txt

echo.
echo [2/3] Configuring credentials (Bot Token & Chat ID)...
python setup_wizard.py

echo.
echo [3/3] Registering global Antigravity MCP server, hooks, and skill...
python install_for_antigravity.py

echo.
set /p AUTO="Enable Friday to automatically start silently on Windows boot? (Y/N): "
if /i "%AUTO%"=="Y" (
    cd /d "%~dp0"
    call enable_autostart.bat
)

echo.
echo ========================================================
echo   🚀 Setup Complete! Friday is active on this laptop.
echo ========================================================
pause
