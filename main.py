from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI
from uvicorn import Config, Server
import asyncio
from config import API_TOKEN
from database.db import init_db
from handlers import commands, server_manage, navigation, alerts
from handlers import admin
from utils.tokens import rotate_tokens_loop
from handlers import notifications
from utils import reports
from aiogram.types import BotCommand
from utils import backup

bot = Bot(API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()
alerts.bot = bot
navigation.bot = bot
server_manage.bot = bot
notifications.bot = bot
reports.bot = bot
admin.bot = bot
backup.bot = bot



async def set_bot_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="Приветствие"),
        BotCommand(command="info", description="Панель управления"),
        BotCommand(command="help", description="Справка и команды"),
        BotCommand(command="notifications", description="Настроить уведомления"),
        BotCommand(command="funcs", description="Сервисные функции")
    ])


# Подключение Telegram-хендлеров
dp.include_router(commands.router)
dp.include_router(server_manage.router)
dp.include_router(navigation.router)
dp.include_router(notifications.router)
dp.include_router(admin.router)

# FastAPI роутер для /alert
alerts.bot = bot  # пробросим бота в модуль
app.include_router(alerts.router)


async def main():
    await init_db()
    await set_bot_commands()
    asyncio.create_task(rotate_tokens_loop())
    asyncio.create_task(reports.loop_daily_reports())
    asyncio.create_task(backup.backup_loop())

    config = Config(app=app, host="0.0.0.0", port=8080, log_level="info")
    server = Server(config)

    polling = asyncio.create_task(dp.start_polling(bot))
    fastapi = asyncio.create_task(server.serve())

    try:
        await asyncio.gather(polling, fastapi)
    except asyncio.CancelledError:
        print("❌ Завершение...")


if __name__ == "__main__":
    asyncio.run(main())

