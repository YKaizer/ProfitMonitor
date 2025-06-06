import asyncio
from database.db import get_servers, get_user_settings, get_all_users, get_report_hour
from handlers.navigation import fetch_data
from aiogram import Bot
from datetime import datetime

bot: Bot = None  # пробрасывается из main

async def loop_daily_reports():
    while True:
        now = datetime.now()
        current_hour = now.hour

        users = await get_all_users()
        for user_id in users:
            settings = await get_user_settings(user_id)
            if not settings["daily_report"]:
                continue

            hour = await get_report_hour(user_id)
            if hour != current_hour:
                continue

            servers = await get_servers(user_id)
            if not servers:
                continue

            report = f"🗓 <b>Ежедневный отчёт</b>\n\n"
            for token, ip, name in servers:
                data, error = await fetch_data(user_id, token)
                if error:
                    report += f"❌ <b>{name or ip}</b>: {error}\n\n"
                    continue

                sys = data["system"]
                mem = sys["memory"]
                disk = sys["disk"]
                cpu = sys["cpu_percent"]
                report += f"""<b>{name or ip}</b>
🧠 CPU: {cpu}%
💾 RAM: {mem['percent']}% ({mem['used'] // 2**20} / {mem['total'] // 2**20} MB)
💽 Disk: {disk['percent']}% ({disk['used'] // 2**30} / {disk['total'] // 2**30} GB)
📦 Контейнеров: {len(data['docker'])}
🎯 Процессов: {len(data['background'])}
⚙️ Сервисов: {sum(1 for s in data['systemd'].values() if s != 'not found')}

"""

            chunks = [report[i:i+4000] for i in range(0, len(report), 4000)]
            for chunk in chunks:
                await bot.send_message(user_id, chunk, parse_mode="HTML")


        await asyncio.sleep(3600)  # проверяем каждый час
