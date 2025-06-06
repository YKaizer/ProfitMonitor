from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import (
    get_user_settings,
    toggle_daily_report,
    get_servers_extended,
    toggle_server_alert,
)
from aiogram import Bot
from datetime import datetime
from aiogram.types import User
import aiohttp


router = Router()
bot: Bot = None


def get_notification_keyboard(settings, servers):
    keyboard = []
    for token, ip, name, flag in servers:
        title = name or ip
        keyboard.append([
            InlineKeyboardButton(
                text=f"{title}: {'Вкл 🟢' if flag else 'Выкл 🔴'}",
                callback_data=f"toggle_server_{token}"
            )
        ])
    keyboard.append([
        InlineKeyboardButton(
            text=f"Ежедневный отчёт: {'Вкл 🟢' if settings['daily_report'] else 'Выкл 🔴'}",
            callback_data="toggle_daily",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(F.text == "/notifications")
async def show_notifications(message: Message):
    settings = await get_user_settings(message.from_user.id)
    servers = await get_servers_extended(message.from_user.id)
    await message.answer(
        "Настройки уведомлений:",
        reply_markup=get_notification_keyboard(settings, servers),
    )

@router.callback_query(F.data.startswith("toggle_server_"))
async def toggle_server(callback: CallbackQuery):
    user: User = callback.from_user
    user_id = user.id
    token = callback.data.replace("toggle_server_", "")

    await toggle_server_alert(user_id, token)

    # получение свежих данных для клавиатуры и рассылки на агент
    servers = await get_servers_extended(user_id)
    server = next((s for s in servers if s[0] == token), None)
    if server:
        ip = server[1]
        flag = bool(server[3])
        await send_alert_mode_to_agent(ip, token, flag)

    settings = await get_user_settings(user_id)
    await callback.message.edit_reply_markup(
        reply_markup=get_notification_keyboard(settings, servers)
    )
    await callback.answer("Изменено.")



@router.callback_query(F.data == "toggle_daily")
async def toggle_daily(callback: CallbackQuery):
    user: User = callback.from_user
    user_id = user.id
    username = user.username or f"no_username:{user_id}"

    await toggle_daily_report(user_id)
    settings = await get_user_settings(user_id)

    if settings["daily_report"]:
        hour = datetime.now().hour
        from database.db import update_report_hour
        await update_report_hour(user_id, hour)
        print(f"Ежедневный репорт [DAILY ON] {user_id} | {username} | hour={hour}")
    else:
        print(f"Ежедневный репорт [DAILY OFF] {user_id} | {username}")

    servers = await get_servers_extended(user_id)
    await callback.message.edit_reply_markup(
        reply_markup=get_notification_keyboard(settings, servers)
    )
    await callback.answer("Изменено.")

async def send_alert_mode_to_agent(ip: str, token: str, alerts_enabled: bool):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://{ip}/set_alert_mode"  # IP уже с портом 8844
            payload = {
                "token": token,
                "enabled": alerts_enabled
            }
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    print(f"✅ Alert mode установлен на агенте {ip}: {alerts_enabled}")
                else:
                    print(f"⚠️ Ошибка установки alert mode на агенте {ip}: статус {resp.status}")
    except Exception as e:
        print(f"❌ Ошибка отправки запроса на агент {ip}: {e}")
