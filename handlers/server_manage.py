from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from fsm.states import AddServerState
from database.db import add_server, get_servers, delete_server, get_notify_alerts_for_user
from handlers.notifications import send_alert_mode_to_agent
from utils.keyboard import get_info_keyboard
import uuid

router = Router()
bot: Bot = None  # ← будет задан в main.py

@router.callback_query(F.data == "add_server")
async def add_server_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()

    token = str(uuid.uuid4())
    await state.update_data(token=token)

    await bot.send_message(
        callback.from_user.id,
        f"🔑 Токен создан:\n\n`{token}`\n\n📨 Теперь введите IP:PORT для привязки сервера:",
        parse_mode="Markdown"
    )
    await state.set_state(AddServerState.waiting_for_ip)

@router.message(AddServerState.waiting_for_ip)
async def process_ip(message: Message, state: FSMContext):
    ip = message.text.strip()
    await state.update_data(ip=ip)
    await message.answer("📝 Введите название сервера (до 16 символов, одно слово):")
    await state.set_state(AddServerState.waiting_for_name)

@router.message(AddServerState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip().replace(" ", "_")[:16]
    data = await state.get_data()
    token = data["token"]
    flag = await get_notify_alerts_for_user(message.chat.id)
    await add_server(message.chat.id, token, data["ip"], name, int(flag))
    await message.answer(f"✅ Сервер {data['ip']} добавлен как `{name}`", parse_mode="Markdown")
    await send_alert_mode_to_agent(data["ip"], token, flag)
    await state.clear()

@router.callback_query(F.data == "list_servers")
async def list_servers(callback: CallbackQuery):
    user_id = callback.from_user.id
    servers = await get_servers(user_id)
    await callback.message.delete()
    await callback.answer()
    if not servers:
        await bot.send_message(user_id, "📭 У вас нет добавленных серверов.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{name} — {ip}", callback_data=f"nav_report_{token}")]
        for token, ip, name in servers
    ])
    await bot.send_message(user_id, "📋 Ваши сервера:\nНажмите, чтобы получить отчёт:", reply_markup=keyboard)

@router.callback_query(F.data == "delete_server")
async def delete_server_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.answer()

    servers = await get_servers(callback.from_user.id)
    if not servers:
        await bot.send_message(callback.from_user.id, "📭 У вас нет серверов для удаления.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🗑 {s[2] or s[1]}", callback_data=f"confirm_delete_{s[0]}")]
            for s in servers
        ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="info")]]
    )

    await bot.send_message(callback.from_user.id, "Выберите сервер для удаления:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete(callback: CallbackQuery):
    token = callback.data.replace("confirm_delete_", "")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_final_{token}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="info")]
    ])

    await callback.message.edit_text(
        "❗️Вы уверены, что хотите удалить сервер?",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("delete_final_"))
async def delete_final(callback: CallbackQuery):
    token = callback.data.replace("delete_final_", "")
    user_id = callback.from_user.id

    await delete_server(user_id, token)
    await callback.message.delete()
    await bot.send_message(user_id, "🗑 Сервер удалён.", reply_markup=get_info_keyboard())


