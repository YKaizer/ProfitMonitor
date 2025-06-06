import asyncio
import uuid
import random
import aiosqlite
import aiohttp
from pathlib import Path

DB_PATH = Path("bot_data.db")

async def rotate_token_for(ip: str, old_token: str):
    new_token = str(uuid.uuid4())
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://{ip}/update_token",
                json={"new_token": new_token},
                timeout=10
            ) as resp:
                if resp.status == 200:
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("UPDATE servers SET token = ? WHERE token = ?", (new_token, old_token))
                        await db.execute("INSERT INTO token_history (token, ip) VALUES (?, ?)", (new_token, ip))
                        await db.commit()
                    print(f"✅ Токен обновлён для {ip}")
                else:
                    print(f"❌ {ip} вернул статус {resp.status}")
    except Exception as e:
        print(f"⚠️ Ошибка при обновлении токена {ip}: {e}")

async def rotate_tokens_loop():
    print("rotate_tokens_loop - Запущена функция")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT ip, token FROM servers")
        servers = await cursor.fetchall()

    for ip, token in servers:
        asyncio.create_task(schedule_token_rotation(ip))  # передаём только IP


async def schedule_token_rotation(ip: str):
    while True:
        delay = random.randint(2400, 3600)
        await asyncio.sleep(delay)

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT token FROM servers WHERE ip = ?", (ip,))
            row = await cursor.fetchone()
            if row:
                current_token = row[0]
                await rotate_token_for(ip, current_token)

  # перезапуск проверки
