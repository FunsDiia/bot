import os
import json
import requests
import time
from subprocess import run

VALUES_FILE = 'values.json'
OFFSET_FILE = '.bot_offset'

def load_values():
    if os.path.exists(VALUES_FILE):
        try:
            with open(VALUES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print("Помилка парсингу values.json:", e)
    return {"expirationTime": "2026-12-31T23:59"}

def save_values(data):
    with open(VALUES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_offset():
    if os.path.exists(OFFSET_FILE):
        try:
            with open(OFFSET_FILE, 'r') as f:
                return int(f.read().strip())
        except:
            return 0
    return 0

def save_offset(offset):
    with open(OFFSET_FILE, 'w') as f:
        f.write(str(offset))

# Завантажуємо значення з файлу
values_data = load_values()

# Спочатку шукаємо токен в values.json, якщо немає - в GitHub Secrets
BOT_TOKEN = values_data.get('tgBotToken') or os.environ.get('BOT_TOKEN')
ADMIN_CHAT_ID = values_data.get('tgChatId') or os.environ.get('ADMIN_CHAT_ID')

if not BOT_TOKEN or not ADMIN_CHAT_ID:
    print("❌ Не вказані BOT_TOKEN або ADMIN_CHAT_ID (ні в values.json, ні в Secrets). Завершення підключення.")
    exit(1)

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text):
    try:
        requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        })
    except Exception as e:
        print("Помилка відправки Telegram повідомлення:", e)

def main():
    print("✅ Бот успішно запущено. Режим: Long-Polling (Безперервний моніторинг)")
    
    # Бот працюватиме приблизно 4 хв 30 сек.
    # Оскільки GitHub Actions перезапускає його кожні 5 хвилин, він буде завжди "в онлайні" без крашів
    # Це дозволяє забезпечити 100% аптайм на безкоштовному тарифі GitHub Actions.
    start_time = time.time()
    max_run_time = 270 
    
    while time.time() - start_time < max_run_time:
        offset = get_offset()
        try:
            # Long-polling на 30 секунд. Бот миттєво відреагує на повідомлення
            req = requests.get(f"{API_URL}/getUpdates?offset={offset}&timeout=30", timeout=35)
            data = req.json()
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            print("Очікування з'єднання...", type(e).__name__)
            time.sleep(2)
            continue

        if not data.get('ok') or not data.get('result'):
            continue

        values = load_values()
        
        # Дописуємо конфіг для відкритості
        if 'tgBotToken' not in values and BOT_TOKEN:
            values['tgBotToken'] = BOT_TOKEN
        if 'tgChatId' not in values and ADMIN_CHAT_ID:
            values['tgChatId'] = ADMIN_CHAT_ID

        values_changed = False
        new_offset = offset

        for update in data['result']:
            new_offset = update['update_id'] + 1
            
            if 'message' not in update or 'text' not in update['message']:
                continue
                
            msg_text = update['message']['text'].strip()
            chat_id = str(update['message']['chat']['id'])

            # Захист: бот чує тільки адміна (Ваш ChatID)
            if chat_id != str(ADMIN_CHAT_ID):
                # send_message(chat_id, "⛔️ Доступ заборонено. Я особистий бот управління системою.")
                continue

            if msg_text.startswith('/start'):
                send_message(chat_id, (
                    "🚀 <b>Система управління додатком активна!</b>\n\n"
                    "👁‍🗨 Я працюю у фоновому режимі та перехоплюю всі дані користувачів (Гео, IP-адресу, пристрій, оновлення анкети) та надсилаю їх сюди миттєво.\n\n"
                    "🛠 <b>Мої команди:</b>\n"
                    "<code>/status</code> - поточна дата доступу до додатку\n"
                    "<code>/setdate YYYY-MM-DDTHH:MM</code> - встановити нову дату закінчення доступу\n"
                    "<code>/info</code> - перевірка роботи та активності сервера"
                ))
                
            elif msg_text.startswith('/status'):
                current_date = values.get('expirationTime', 'Не встановлено')
                send_message(chat_id, f"📅 Поточний термін дії: <b>{current_date}</b>")
                
            elif msg_text.startswith('/info'):
                uptime = int(time.time() - start_time)
                send_message(chat_id, f"🟢 <b>Сервер: Активний (Long-Polling)</b>\n⌚️ Безперервна сесія (Uptime): {uptime}/270 сек.\n♻️ Захищений моніторинг через GitHub Actions працює штатно.")

            elif msg_text.startswith('/setdate'):
                parts = msg_text.split()
                if len(parts) == 2:
                    new_date = parts[1]
                    values['expirationTime'] = new_date
                    values_changed = True
                    send_message(chat_id, f"⏳ Застосовую дату... <b>{new_date}</b>\nТриває синхронізація з базою та автоматичне оновлення застосунку...")
                else:
                    send_message(chat_id, "⚠️ Неправильний формат.\nПриклад:\n<code>/setdate 2026-12-31T23:59</code>")

        save_offset(new_offset)

        # Якщо дані змінені - автоматично комітимо і пушимо.
        if values_changed:
            save_values(values)
            print("Дані були змінені. Пушимо на GitHub...")
            try:
                run(["git", "config", "--global", "user.name", "github-actions[bot]"])
                run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"])
                run(["git", "add", "values.json", ".bot_offset"])
                run(["git", "commit", "-m", "bot: settings updated via Telegram"])
                run(["git", "push"])
                send_message(str(ADMIN_CHAT_ID), "✅ <b>Успішно!</b> Значення оновлено на хостингу. Клієнти підтягнуть нову дату автоматично під час роботи.")
            except Exception as e:
                send_message(str(ADMIN_CHAT_ID), f"❌ Помилка завантаження на хостинг: {e}")

if __name__ == '__main__':
    main()
