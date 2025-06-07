from fastapi import APIRouter, Request
from aiogram import Bot
from database.db import get_user_by_token, get_ip

router = APIRouter()
bot: Bot = None  # присваивается в main.py

@router.post("/alert")
async def handle_alert(request: Request):
    data = await request.json()

    token = data.get("token")
    message = data.get("message")
    percent = data.get("percent", None)

    if not token:
        return {"status": "no token"}

    row = await get_user_by_token(token)
    if not row:
        return {"status": "unauthorized"}

    user_id, name, ip_db = row
    name = name or "Без имени"
    ip = await get_ip(token)
    if message:
        text = f"⚠️ Уведомление от `{name}` ({ip}):\n\n{message}"
    elif percent:
        text = f"⚠️ Сервер `{name}` ({ip}) почти забит (диск > 95%)!\nДиск: {percent}%\n\n⏳ Перезапущен docker-compose Ritual."
    else:
        text = f"⚠️ Пришёл неизвестный алерт с сервера `{name}` ({ip})"

    await bot.send_message(user_id, text, parse_mode="Markdown")
    return {"status": "ok"}
