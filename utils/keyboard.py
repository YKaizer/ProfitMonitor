from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_nav_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Отчёт", callback_data=f"nav_report_{token}"),
            InlineKeyboardButton(text="🧩 Ноды", callback_data=f"nav_nodes_{token}")
        ],
        [
            InlineKeyboardButton(text="🎯 Процессы", callback_data=f"nav_processes_{token}"),
            InlineKeyboardButton(text="⚙️ Сервисы", callback_data=f"nav_services_{token}")
        ],
        [   
            InlineKeyboardButton(text="🐳 Докер", callback_data=f"nav_docker_{token}"),
            InlineKeyboardButton(text="📝 Комментарий", callback_data=f"edit_note_{token}")
        ]
    ])


def get_info_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Подключить сервер", callback_data="add_server")],
        [InlineKeyboardButton(text="📋 Список серверов", callback_data="list_servers")],
        [InlineKeyboardButton(text="❌ Удалить сервер", callback_data="delete_server")]
    ])

def get_funcs_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♻ Перезапуск Ritual", callback_data="restart_ritual")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="info")]
    ])
