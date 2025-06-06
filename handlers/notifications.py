from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import get_user_settings, toggle_notify_alerts, toggle_daily_report
from aiogram import Bot
from datetime import datetime
from aiogram.types import User
from database.db import get_servers
import aiohttp


router = Router()
bot: Bot = None


def get_notification_keyboard(settings):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"Уведомления об упавших нодах: {'Вкл 🟢' if settings['notify_alerts'] else 'Выкл 🔴'}",
            callback_data="toggle_alerts"
        )],
        [InlineKeyboardButton(
            text=f"Ежедневный отчёт: {'Вкл 🟢' if settings['daily_report'] else 'Выкл 🔴'}",
            callback_data="toggle_daily"
        )]
    ])

@router.message(F.text == "/notifications")
async def show_notifications(message: Message):
    settings = await get_user_settings(message.from_user.id)
    await message.answer("Настройки уведомлений:", reply_markup=get_notification_keyboard(settings))

@router.callback_query(F.data == "toggle_alerts")
async def toggle_alerts(callback: CallbackQuery):
    user: User = callback.from_user
    user_id = user.id
    username = user.username or f"no_username:{user_id}"

    await toggle_notify_alerts(user_id)
    settings = await get_user_settings(user_id)

    if settings["notify_alerts"]:
        print(f"Уведомления о падающих нодах [FALL ALERTS ON] {user_id} | {username}")
    else:
        print(f"Уведомления о падающих нодах [FALL ALERTS OFF] {user_id} | {username}")

    # 🔁 Рассылаем настройку на все сервера
    servers = await get_servers(user_id)
    for token, ip, _ in servers:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"http://{ip}/set_alert_mode", json={"enabled": settings["notify_alerts"]}) as resp:
                    await resp.read()
            print(f"✅ Отправлен режим alerts_enabled={settings['notify_alerts']} на {ip}")
        except Exception as e:
            print(f"❌ Не удалось отправить на {ip}: {e}")

    await callback.message.edit_reply_markup(reply_markup=get_notification_keyboard(settings))
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

    await callback.message.edit_reply_markup(reply_markup=get_notification_keyboard(settings))
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
