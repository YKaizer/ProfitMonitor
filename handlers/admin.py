from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from fsm.states import BroadcastState
from database.db import (
    get_all_users,
    get_user_count,
    get_server_count,
)
from utils.backup import BACKUP_DIR
from aiogram.types import FSInputFile
import os

router = Router()
bot: Bot = None

ADMIN_ID = 422955762

@router.message(Command("send_mes"))
async def send_mes(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /send_mes <сообщение>")
        return
    text = parts[1]
    await state.set_state(BroadcastState.waiting_for_confirm)
    await state.set_data({"text": text})
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")],
        ]
    )
    await message.answer(f"Отправить сообщение всем пользователям?\n\n{text}", reply_markup=keyboard)


@router.callback_query(F.data == "broadcast_confirm")
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    data = await state.get_data()
    text = data.get("text")
    await state.clear()
    await callback.message.edit_text("⏳ Рассылка...")
    users = await get_all_users()
    count = 0
    for uid in users:
        try:
            await bot.send_message(uid, text)
            count += 1
        except Exception as e:
            print(f"Не удалось отправить сообщение пользователю {uid}: {e}")
    await callback.message.edit_text(f"✅ Рассылка завершена. Отправлено {count} пользователям.")


@router.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text("Рассылка отменена.")

@router.message(Command("get_backup"))
async def get_backup_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    files = [f for f in os.listdir(BACKUP_DIR) if f.startswith("bot_data_")]
    if not files:
        await message.answer("Нет доступных бэкапов.")
        return

    latest = sorted(files)[-1]
    path = os.path.join(BACKUP_DIR, latest)
    await message.answer_document(FSInputFile(path))


@router.message(Command("get_info"))
async def get_info_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = await get_user_count()
    servers = await get_server_count()
    text = (
        f"👥 Пользователей зарегистрировано: {users}\n"
        f"🖥️ Добавлено серверов: {servers}"
    )
    await message.answer(text)
