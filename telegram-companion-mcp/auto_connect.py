import time
import httpx

TOKEN = "8914563827:AAFl-RTvzL2iuanXl-kD_93vAvE2fIEvIqU"
url = f"https://api.telegram.org/bot{TOKEN}"

print("Listening for your message in @Friday830bot...")
start = time.time()
found = False

with httpx.Client(timeout=35.0) as client:
    while time.time() - start < 60:
        try:
            r = client.get(f"{url}/getUpdates", params={"timeout": 10})
            data = r.json()
            if data.get("ok") and data.get("result"):
                for upd in data["result"]:
                    msg = upd.get("message") or upd.get("my_chat_member")
                    if msg:
                        chat = msg.get("chat", {})
                        chat_id = chat.get("id")
                        first_name = chat.get("first_name", "Friend")
                        if chat_id:
                            print(f"SUCCESS: Found Chat ID {chat_id} from {first_name}")
                            # Save to .env
                            env_content = f'TELEGRAM_BOT_TOKEN="{TOKEN}"\nTELEGRAM_CHAT_ID="{chat_id}"\n'
                            with open(r"d:\dev\projects\exploring\telegram-companion-mcp\.env", "w") as f:
                                f.write(env_content)
                            print("Saved to .env successfully!")
                            
                            # Send welcome message
                            client.post(f"{url}/sendMessage", json={
                                "chat_id": chat_id,
                                "text": f"🎉 *Connected!*\n\nHello {first_name}! Antigravity is now successfully connected to your mobile phone wirelessly.\n\nYou can now receive updates and approve tasks from here.",
                                "parse_mode": "Markdown"
                            })
                            found = True
                            break
            if found:
                break
        except Exception as e:
            print("Polling error:", e)
            time.sleep(2)

if not found:
    print("TIMEOUT: No message received within 60 seconds.")

