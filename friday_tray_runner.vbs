' Friday System Tray Silent Launcher (Zero Console Window)
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\dev\projects\Antigravity remove chat tool\telegram-companion-mcp"
WshShell.Run """C:\Users\rites\AppData\Local\Programs\Python\Python313\pythonw.exe"" ""D:\dev\projects\Antigravity remove chat tool\telegram-companion-mcp\system_tray.py""", 0, False
