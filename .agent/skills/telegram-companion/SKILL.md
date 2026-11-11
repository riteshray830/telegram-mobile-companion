---
name: telegram-companion
description: >-
  Connects Antigravity to your mobile phone via Telegram. Use to send push notifications,
  request mobile approval/permission with interactive buttons before sensitive actions,
  prompt for text input, or deliver screenshots, logs, and artifacts directly to mobile.
---

# Telegram Companion Skill

This skill allows Antigravity to interact wirelessly with the user's mobile phone using Telegram.

## When to Use

1. **Permission Requests**:
   - Before executing potentially destructive shell commands (e.g., dropping database tables, deleting folders, `git push --force`, cloud resource deletion).
   - Before applying risky migrations or deploying to production.
   - Use `telegram_ask_permission(prompt, options=["Approve", "Reject"], timeout_seconds=120)`.
   - **Crucial**: If the response is not `"Approve"`, abort the action immediately.

2. **Long-Running Task Completion**:
   - Notify the user when an extensive background task, test suite, or long build finishes.
   - Use `telegram_notify(message)`.

3. **Remote Input Needed**:
   - When the agent is waiting on user input (e.g., clarification, token, preference) and the user is away from their keyboard.
   - Use `telegram_ask_text(prompt)`.

4. **Delivering Artifacts & Visuals**:
   - Use `telegram_send_photo(photo_path, caption)` to send screenshots or UI previews.
   - Use `telegram_send_file(file_path, caption)` to send generated PDFs, logs, or reports.

## Safety & Security Protocols
- Never transmit raw API secret keys, passwords, or credentials in plain text over Telegram.
- Always observe default-to-deny: any timeout or non-approval must be treated as a rejection.

