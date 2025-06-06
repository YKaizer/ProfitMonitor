import os
import shutil
import asyncio
from datetime import datetime

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
        except Exception as e:
            print(f"❌ Ошибка бэкапа: {e}")

        await asyncio.sleep(3600)  # раз в час
