# 📱 Telegram Companion for Antigravity

Wirelessly connects your Antigravity coding agent to your mobile phone via Telegram.
Enables instant push notifications, interactive approval buttons (`[Approve]` / `[Reject]`), mobile text replies, and direct file/photo delivery.

---

## 🚀 2-Minute Setup

### Step 1: Create your Telegram Bot
1. Open Telegram on your phone and search for **`@BotFather`**.
2. Tap **Start** and send the command:
   ```text
   /newbot
   ```
3. Follow the prompts to choose a name and a username (e.g. `MyAgyDevBot`).
4. `@BotFather` will give you a **Bot Token** (looks like `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`). Copy it.

### Step 2: Get your Numeric User ID
1. On Telegram, search for **`@userinfobot`**.
2. Tap **Start**. It will reply with your personal numeric **Id** (e.g. `123456789`). Copy it.
3. Open your newly created bot chat from Step 1 and tap **Start** (this allows the bot to message you).

### Step 3: Configure `.env`
Create a `.env` file in this directory (`d:\dev\projects\exploring\telegram-companion-mcp\.env`) with:
```env
TELEGRAM_BOT_TOKEN="your_bot_token_from_step_1"
TELEGRAM_CHAT_ID="your_numeric_id_from_step_2"
```

---

## 🛠 Available Tools

| Tool | Description |
| :--- | :--- |
| `telegram_notify(message)` | Sends instant alerts, build updates, or task completion messages. |
| `telegram_ask_permission(prompt, options, timeout_seconds)` | Sends interactive buttons (`[Approve]`, `[Reject]`) and waits for your tap. Auto-denies on timeout. |
| `telegram_ask_text(prompt, timeout_seconds)` | Sends a prompt and waits for you to reply with text from your phone. |
| `telegram_send_photo(photo_path, caption)` | Sends screenshots, plots, or UI preview images. |
| `telegram_send_file(file_path, caption)` | Sends log files, diffs, reports, or artifacts. |
| `telegram_update_progress(message_id, text)` | Edits an existing message in-place for live progress bars. |
| `telegram_test_connection()` | Validates bot token, bot name, and target chat ID. |

---

## 🔒 Security Protections
- **Sender ID Validation**: Every incoming interaction checks `sender_id == TELEGRAM_CHAT_ID`. Taps or messages from any other account are rejected immediately.
- **Fail-Safe Default-to-Deny**: Any timeout, network hiccup, or unknown response automatically rejects the permission request.
- **Outbound Only**: Uses Telegram long-polling. No open ports, ngrok tunnels, or public IP exposure required on your PC.

