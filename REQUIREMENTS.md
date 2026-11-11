# 📦 Requirements & Multi-Platform Setup Guide

This guide details everything required to install and run the **Telegram Mobile Companion & Remote Dev Assistant** on **any laptop** (Windows, macOS, Linux) with **any chatbot / AI backend**.

---

## 💻 System Prerequisites

1. **Operating System**:
   - Windows 10/11
   - macOS (Apple Silicon or Intel)
   - Linux (Ubuntu, Debian, Fedora, Arch, etc.)
2. **Python**:
   - Python **3.10** or higher (Python 3.12 / 3.13 recommended)
3. **Package Manager** *(Recommended)*:
   - [`uv`](https://docs.astral.sh/uv/) for instant, zero-setup dependency management:
     - **Windows**: `winget install astral-sh.uv` or `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
     - **macOS / Linux**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
4. **Git**:
   - Installed and available on system PATH (`git --version`).

---

## 🤖 Supported AI Chatbots & Backends

When you install this tool, you can select which AI backend powers your assistant:

| Backend | Description | Requirements |
| :--- | :--- | :--- |
| **`antigravity`** *(Default)* | Directly connects to your active Google Antigravity IDE coding session on your PC. Full terminal and code tool access. | Antigravity CLI (`agy`) installed on laptop. |
| **`gemini`** | Standalone Google Gemini AI. Chat and ask questions about your workspace from anywhere. | Free API Key from [Google AI Studio](https://aistudio.google.com/). |
| **`openai`** | OpenAI GPT-4o / GPT-4o-mini. | OpenAI API Key (`sk-...`). |
| **`claude`** | Anthropic Claude 3.5 Sonnet / Haiku. | Anthropic API Key (`sk-ant-...`). |
| **`ollama`** | 100% Local, private, offline LLM (Llama 3, Qwen, DeepSeek). Zero data leaves your laptop. | [Ollama](https://ollama.com/) running locally. |

---

## 🚀 3-Step Setup on Any New Laptop

### Step 1: Clone the Repository
```bash
git clone https://github.com/riteshray830/telegram-mobile-companion.git
cd telegram-mobile-companion
```

### Step 2: Run the Interactive Setup Wizard
Run the setup command:
```bash
# Using uv (no virtual environment creation needed):
uv run telegram-companion-mcp/setup_wizard.py

# Or using standard python:
python telegram-companion-mcp/setup_wizard.py
```

The interactive wizard will prompt you step-by-step:
1. **Workspace Root**: Specify the root dev folder you want to explore (e.g. `D:\dev`, `~/dev`, or current folder).
2. **AI Backend**: Choose between `antigravity`, `gemini`, `openai`, `claude`, or `ollama`.
3. **API Key**: If using cloud LLMs, enter your API key.
4. **Telegram Bot Token**: Paste the token from `@BotFather`.
5. **Chat ID**: Enter your numeric ID or choose **Auto-Detect** (the wizard will wait for you to tap Start on Telegram and grab it automatically!).

### Step 3: Start the Assistant
```bash
# Windows:
start_friday.bat

# Or any platform (Windows, macOS, Linux):
python telegram-companion-mcp/friday_runner.py
# (Or using uv):
uv run telegram-companion-mcp/friday_runner.py
```

---

## 🔒 Security & Privacy Guarantees

* **Zero Cloud Token Storage**: All tokens, API keys, and user IDs are saved exclusively in a local `.env` file on your laptop.
* **Strict Git Exclusion**: `.env`, virtual environments, and caches are listed in `.gitignore` and **will never be uploaded to GitHub**.
* **User ID Locking**: The bot rejects messages from any Telegram user ID other than the configured owner.
* **No Inbound Open Ports**: Uses Telegram HTTPS long-polling. No ngrok, port forwarding, or exposed local servers required.

