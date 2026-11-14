---
name: telegram-companion
description: Two-way Telegram mobile companion and remote dev controller. Use when the user asks to send notifications or files to Telegram, request interactive permissions from mobile, capture webcam or screenshot, query laptop battery/stats, or manage remote dev watchdogs.
---

# Telegram Mobile Companion & Remote Dev Controller

This skill allows Antigravity to interact directly with the user's mobile phone via Telegram and query/control hardware on their laptop.

## Available Capabilities & MCP Tools

### 1. Mobile Notifications & Approvals
- `telegram_notify(message)`: Sends instant push notifications and status updates to the user's phone.
- `telegram_ask_permission(prompt)`: Prompts the user on Telegram with interactive `[Approve]` and `[Reject]` inline buttons. Waits for mobile response before proceeding.
- `telegram_ask_text(prompt)`: Asks the user an open-ended question on Telegram and waits for their typed response.
- `telegram_send_photo(photo_path, caption)`: Sends an image or screenshot to Telegram.
- `telegram_send_file(file_path, caption)`: Delivers any document or source file directly to the user's phone.

### 2. Remote Laptop Diagnostics & Hardware Controls
- `laptop_battery_status()`: Checks current battery percentage, charging state, cycle count, and health.
- `laptop_system_health()`: Reads real-time CPU utilization, RAM usage, and available disk space.
- `laptop_wifi_status()`: Reports connected Wi-Fi SSID and signal strength.
- `laptop_top_processes()`: Lists the highest memory-consuming processes.
- `laptop_kill_process(target)`: Safely terminates a hung or runaway process by PID or name.
- `laptop_screenshot()`: Takes a screenshot of the primary display and sends it to Telegram.
- `laptop_webcam_snap()`: Captures a photo from the laptop's front webcam and delivers it to Telegram.
- `laptop_lock()`: Locks the Windows workstation for security.

### 3. Productivity & Dev Watchdogs
- `laptop_clipboard_get()`: Reads current text on the laptop's clipboard.
- `laptop_clipboard_set(text)`: Writes text to the laptop's clipboard ready for Ctrl+V.
- `laptop_git_status(repo_hint)`: Reports dirty status, uncommitted files, and branch details for any git repo in D:\dev.
- `laptop_watch_dev_server(target, action)`: Adds or removes local ports (e.g. 3000, 8080) to the crash watchdog.
- `laptop_open_browser(url, profile_name)`: Launches Google Chrome directly into a specific profile, bypassing the profile picker.
- `laptop_launch_app(app_target)`: Opens desktop apps (VS Code, Explorer, Terminal, Calculator, etc.).

## Best Practices
- When executing critical, irreversible actions (e.g., dropping a database, deleting production files, or running heavy deployment scripts), call `telegram_ask_permission` to get mobile approval first.
- Keep notification messages concise and use Markdown bolding/emojis for high readability on small mobile screens.
