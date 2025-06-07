from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from utils.keyboard import get_info_keyboard, get_funcs_keyboard
from database.db import get_user_settings
from handlers.notifications import get_notifications_main_keyboard
from aiogram.types import FSInputFile

router = Router()

@router.message(Command("start"))
async def start_command(message: Message):
    # Ensure the user exists in the database so that broadcasts reach them
    await get_user_settings(message.from_user.id)
    photo = FSInputFile("welcome_monitor.png")
    await message.answer_photo(
        photo=photo,
        caption="🟣 Добро пожаловать в *ProfitNodes Monitor*!\n\n"
        "Чтобы узнать как пользоваться - введите /help\n"
        "Чтобы начать - введите /info\n\n"
        "⚙️ Монитор в бета-тестировании\n"
        "В дальнейшем будет обновляться функционал",
        parse_mode="Markdown"
    )

@router.message(Command("help"))
async def help_command(message: Message):
    text = (
        "🌐 Для работы с ботом изучите эту [статью](https://www.notion.so/1e1a0f0bff2d809d8e5bf79ce2f21a75) и [видео](https://www.youtube.com/watch?v=y4x8mD2uGQI)\n\n\n"
        "ℹ️ *Справка по командам:*\n\n"
        "/info — панель управления\n"
        "/notifications — настроить уведомления\n"
        "/funcs — функции в один клик \n\n"
        "/start — приветствие\n"
        "/help — справка и помощь\n\n"
        "💬 По всем вопросам пишите в наш приватный чат"
    )
    await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)

@router.message(Command("info"))
async def info_command(message: Message):
    await message.answer("🖥️ Панель управления", reply_markup=get_info_keyboard())

@router.callback_query(F.data == "info")
async def info_callback(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()
    await callback.message.answer("🖥️ Панель управления", reply_markup=get_info_keyboard())

@router.message(Command("notifications"))
async def notifications_command(message: Message):
    # загружаем настройки пользователя для отображения меню
    settings = await get_user_settings(message.from_user.id)
    await message.answer(
        "🔔 Настройки уведомлений",
        # основной экран уведомлений требует только текущие настройки
        reply_markup=get_notifications_main_keyboard(settings),
    )

@router.message(Command("funcs"))
async def funcs_command(message: Message):
    await message.answer("🚀 Функции в один клик", reply_markup=get_funcs_keyboard())
