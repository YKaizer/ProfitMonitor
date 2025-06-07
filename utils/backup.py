import os
import shutil
import asyncio
from datetime import datetime
from aiogram import Bot

bot: Bot = None  # will be set in main.py
ADMIN_ID = 422955762

BACKUP_SOURCE = "/root/profit_monitor/bot_data.db"
BACKUP_DIR = "/root/db_backups_profit_monitor/"

async def backup_loop():
    os.makedirs(BACKUP_DIR, exist_ok=True)

    while True:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M")
        backup_path = os.path.join(BACKUP_DIR, f"bot_data_{now}.db")

        try:
            shutil.copy2(BACKUP_SOURCE, backup_path)
            print(f"✅ Бэкап создан: {backup_path}")

            if bot is not None:
                await bot.send_document(ADMIN_ID, open(backup_path, "rb"))
                print("📤 Бэкап отправлен администратору")
        except Exception as e:
            print(f"❌ Ошибка бэкапа: {e}")

        await asyncio.sleep(86400)  # раз в 24 часа
