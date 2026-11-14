@echo off
title Stop Friday Remote Companion
echo ========================================================
echo   🛑 Stopping Friday Remote Companion...
echo ========================================================
echo.

powershell -NoProfile -Command "$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*friday_runner.py*' }; if ($procs) { foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force; Write-Host ('   [+] Terminated Friday process (PID: ' + $p.ProcessId + ')') -ForegroundColor Green; } } else { Write-Host '   [i] No active Friday processes found.' -ForegroundColor Yellow; }"

echo.
echo ========================================================
echo   ✅ Friday has been stopped.
echo ========================================================
timeout /t 3 >nul
