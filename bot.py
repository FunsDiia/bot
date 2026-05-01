import os
import json
import requests

# Змінні оточення з GitHub Secrets
BOT_TOKEN = os.environ.get('8761188502:AAF0XbKry5t6VSP5Sm0Td9F2_13GXeuH3dg')
ADMIN_CHAT_ID = os.environ.get('-1002003419071')

if not BOT_TOKEN or not ADMIN_CHAT_ID:
    print("Не вказані BOT_TOKEN або ADMIN_CHAT_ID")
    exit(1)

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
VALUES_FILE = 'values.json'
OFFSET_FILE = '.bot_offset'

def get_offset():
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE, 'r') as f:
            return int(f.read().strip())
    return 0

def save_offset(offset):
    with open(OFFSET_FILE, 'w') as f:
        f.write(str(offset))

def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })

def load_values():
    if os.path.exists(VALUES_FILE):
        try:
            with open(VALUES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"expirationTime": "2026-12-31T23:59", "tgBotToken": BOT_TOKEN, "tgChatId": ADMIN_CHAT_ID}

def save_values(data):
    with open(VALUES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def main():
    offset = get_offset()
    try:
        req = requests.get(f"{API_URL}/getUpdates?offset={offset}&timeout=10")
        data = req.json()
    except Exception as e:
        print("Помилка підключення до Telegram:", e)
        return

    if not data.get('ok') or not data.get('result'):
        print("Немає нових повідомлень.")
        return

    values = load_values()
    values_changed = False
    new_offset = offset

    for update in data['result']:
        new_offset = update['update_id'] + 1
        
        if 'message' not in update or 'text' not in update['message']:
            continue
            
        msg_text = update['message']['text'].strip()
        chat_id = str(update['message']['chat']['id'])

        # Захист: відповідаємо лише адміну
        if chat_id != ADMIN_CHAT_ID:
            continue

        if msg_text.startswith('/start'):
            send_message(chat_id, "Привіт! Я бот для керування підпискою додатку.\\n\\nДоступні команди:\\n/status - перевірити поточну дату доступу\\n/setdate YYYY-MM-DDTHH:MM - встановити нову дату (напр. <code>/setdate 2024-12-31T23:59</code>)")
            
        elif msg_text.startswith('/status'):
            current_date = values.get('expirationTime', 'Не встановлено')
            send_message(chat_id, f"📅 Поточний термін дії: <b>{current_date}</b>")
            
        elif msg_text.startswith('/setdate'):
            parts = msg_text.split()
            if len(parts) == 2:
                new_date = parts[1]
                values['expirationTime'] = new_date
                values_changed = True
                send_message(chat_id, f"✅ Дату успішно змінено на <b>{new_date}</b>.\\nЗміни будуть застосовані в додатку після швидкого оновлення GitHub Pages.")
            else:
                send_message(chat_id, "⚠️ Неправильний формат. Використовуй:\\n<code>/setdate 2024-12-31T23:59</code>")

    # Якщо дані змінені - зберігаємо у файл (GitHub Actions потім зробить commit + push)
    if values_changed:
        save_values(values)
        print("Файл values.json оновлено.")

    save_offset(new_offset)
    print("Offset оновлено.")

if __name__ == '__main__':
    main()
