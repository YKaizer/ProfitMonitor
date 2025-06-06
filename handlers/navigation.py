from aiogram import Router, F
from aiogram.types import CallbackQuery
from database.db import get_servers
from utils.keyboard import get_nav_keyboard
from dateutil import parser
from datetime import datetime
import uuid
import aiohttp
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram import Bot
from utils.keyboard import get_nav_keyboard
from aiogram.fsm.context import FSMContext
from fsm.states import CommentState
from database.db import update_note, get_note_and_name
from aiogram.types import Message


bot: Bot = None  # будет присвоен из main.py


router = Router()
LOG_CONTEXTS = {}

async def fetch_data(user_id: int, token: str):
    servers = await get_servers(user_id)
    server = next((s for s in servers if s[0] == token), None)
    if not server:
        return None, "❌ Сервер не найден."
    ip = server[1]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"http://{ip}/ping", json={"token": token}, timeout=10) as resp:
                if resp.status != 200:
                    return None, f"❌ Сервер не отвечает. Код: {resp.status}"
                return await resp.json(), None
    except Exception as e:
        return None, f"❌ Ошибка соединения: {e}"

@router.callback_query(F.data.startswith("nav_report_"))
async def nav_report(callback: CallbackQuery):
    token = callback.data.replace("nav_report_", "")
    user_id = callback.from_user.id
    await callback.message.delete()
    await callback.answer()
    data, error = await fetch_data(user_id, token)
    if error:
        await callback.message.answer(error)
        return

    row = await get_note_and_name(token)
    name = row[0] if row else "Без имени"
    note = row[1] if row and row[1] else ""

    system = data["system"]
    cpu_percent = system["cpu_percent"]
    cores = system.get("cpu_cores", 1)
    load_approx = (cpu_percent / 100) * cores

    mem = system["memory"]
    disk = system["disk"]

    text = f"""🖥 <b>{name}</b>

🧠 CPU: {cpu_percent}% ({load_approx:.1f} / {cores} cores)
💾 RAM: {mem['percent']}% ({mem['used'] / 2**30:.1f} / {mem['total'] / 2**30:.0f} GB)
💽 Disk: {disk['percent']}% ({disk['used'] / 2**30:.1f} / {disk['total'] / 2**30:.0f} GB)
🐳 Docker: {len(data['docker'])} контейнеров
📍 Ноды по процессам: {len(data['background'])} шт.
⚙️ Сервисы: {sum(1 for s in data['systemd'].values() if s == "active")} сервисов
"""

    if note:
        text += f"\n📝 Комментарий:\n{note}"

    await callback.message.answer(text, parse_mode="HTML", reply_markup=get_nav_keyboard(token))

@router.callback_query(F.data.startswith("nav_docker_"))
async def nav_docker(callback: CallbackQuery):
    token = callback.data.replace("nav_docker_", "")
    user_id = callback.from_user.id
    await callback.message.delete()
    await callback.answer()

    data, error = await fetch_data(user_id, token)
    if error:
        await bot.send_message(user_id, error)
        return

    containers = {
        name: info for name, info in data["docker"].items()
        if info.get("status") == "running"
    }

    if not containers:
        await bot.send_message(user_id, "🐳 Нет активных контейнеров.")
        return

    text = f"🐳 Активных контейнеров: {len(containers)}\n"

    for name, info in containers.items():
        try:
            started = parser.isoparse(info["started_at"]).replace(tzinfo=None)
            uptime = datetime.utcnow() - started
            minutes = int(uptime.total_seconds() // 60)
            hours, mins = divmod(minutes, 60)
            if hours >= 48:
                days = hours // 24
                hrs = hours % 24
                text += f"• {name} — {days}d {hrs}h\n"
            else:
                text += f"• {name} — {hours}h {mins}m\n"
        except:
            text += f"• {name} — ?\n"

    keyboard = []
    for name in containers:
        log_id = str(uuid.uuid4())[:8]
        LOG_CONTEXTS[log_id] = (token, name)
        keyboard.append([
            InlineKeyboardButton(text=f"📄 Логи: {name}", callback_data=f"log_docker_{log_id}")
        ])

    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"nav_report_{token}")])

    await bot.send_message(
        user_id,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )



@router.callback_query(F.data.startswith("nav_processes_"))
async def nav_processes(callback: CallbackQuery):
    token = callback.data.replace("nav_processes_", "")
    def builder(data):
        processes = data["background"]
        if not processes:
            return "🎯 Нет активных процессов (нод по процессам не найдено)."
        return "🎯 Обнаружены ноды по процессам:\n" + "\n".join([f"• {name}" for name in processes])
    await render_and_send(callback, token, builder)

@router.callback_query(F.data.startswith("nav_services_"))
async def nav_services(callback: CallbackQuery):
    token = callback.data.replace("nav_services_", "")
    user_id = callback.from_user.id
    await callback.message.delete()
    await callback.answer()

    data, error = await fetch_data(user_id, token)
    if error:
        await bot.send_message(user_id, error)
        return

    services = data["systemd"]
    all_found = {k: v for k, v in services.items() if v != "not found"}
    loggable = {k: v for k, v in all_found.items() if v == "active"}

    if not all_found:
        await bot.send_message(user_id, "⚙️ Активных systemd-сервисов не найдено.")
        return

    text = "⚙️ Активные systemd-сервисы:\n"
    for name, status in all_found.items():
        text += f"• {name} — {status}\n"

    buttons = [
        InlineKeyboardButton(text=f"📄 Логи: {name}", callback_data=f"log_service_{str(uuid.uuid4())[:8]}")
        for name in loggable
    ]

    # сохранить лог-контекст для кнопок
    for button in buttons:
        log_id = button.callback_data.replace("log_service_", "")
        LOG_CONTEXTS[log_id] = (token, button.text.replace("📄 Логи: ", ""))

    keyboard = [[btn] for btn in buttons]
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"nav_report_{token}")])

    await bot.send_message(user_id, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@router.callback_query(F.data.startswith("nav_nodes_"))
async def nav_nodes(callback: CallbackQuery):
    token = callback.data.replace("nav_nodes_", "")
    user_id = callback.from_user.id

    await callback.message.delete()
    await callback.answer()

    servers = await get_servers(user_id)
    server = next((s for s in servers if s[0] == token), None)
    if not server:
        await bot.send_message(user_id, "❌ Сервер не найден.")
        return

    ip = server[1]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://{ip}/nodes", json={"token": token}, timeout=10
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"Код {resp.status}")
                data = await resp.json()
    except Exception as e:
        await bot.send_message(user_id, f"❌ Ошибка запроса /nodes: {e}")
        return

    nodes = data.get("nodes", [])
    if not nodes:
        text = "🧩 На сервере не обнаружено установленных нод."
    else:
        text = "🧩 Установленные ноды:\n" + "\n".join([f"• {n}" for n in nodes])

    await bot.send_message(user_id, text, reply_markup=get_nav_keyboard(token))

@router.callback_query(F.data.startswith("log_service_"))
async def handle_log_service(callback: CallbackQuery):
    log_id = callback.data.replace("log_service_", "")
    if log_id not in LOG_CONTEXTS:
        await callback.answer("⚠️ Истекла кнопка или неизвестный лог", show_alert=True)
        return

    token, service = LOG_CONTEXTS[log_id]
    user_id = callback.from_user.id

    servers = await get_servers(user_id)
    server = next((s for s in servers if s[0] == token), None)
    if not server:
        await bot.send_message(user_id, "❌ Сервер не найден.")
        return

    await callback.message.delete()
    await callback.answer("⏳ Получаю логи...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://{server[1]}/logs_services",
                json={"token": token, "service": service},
                timeout=10
            ) as resp:
                logs = await resp.text()
    except Exception as e:
        await bot.send_message(user_id, f"❌ Ошибка: {e}")
        return

    import html
    logs = html.escape(logs[:4000])  # Экранируем HTML для Telegram

    await bot.send_message(
        user_id,
        f"📄 Логи для `{service}`:\n\n<pre>{logs}</pre>",
        parse_mode="HTML",
        reply_markup=get_nav_keyboard(token)
    )

@router.callback_query(F.data.startswith("log_docker_"))
async def handle_log_docker(callback: CallbackQuery):
    log_id = callback.data.replace("log_docker_", "")
    if log_id not in LOG_CONTEXTS:
        await callback.answer("⚠️ Истекла кнопка или неизвестный лог", show_alert=True)
        return

    token, container = LOG_CONTEXTS[log_id]
    user_id = callback.from_user.id

    servers = await get_servers(user_id)
    server = next((s for s in servers if s[0] == token), None)
    if not server:
        await bot.send_message(user_id, "❌ Сервер не найден.")
        return

    await callback.message.delete()
    await callback.answer("⏳ Получаю логи контейнера...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://{server[1]}/logs_docker",
                json={"token": token, "container": container},
                timeout=10
            ) as resp:
                logs = await resp.text()
    except Exception as e:
        await bot.send_message(user_id, f"❌ Ошибка: {e}")
        return

    import html
    logs = html.escape(logs[:4000])  # Telegram-safe

    await bot.send_message(
        user_id,
        f"📄 Логи контейнера `{container}`:\n\n<pre>{logs}</pre>",
        parse_mode="HTML",
        reply_markup=get_nav_keyboard(token)
    )

async def render_and_send(callback: CallbackQuery, token: str, builder):
    user_id = callback.from_user.id
    await callback.message.delete()
    await callback.answer()

    data, error = await fetch_data(user_id, token)
    if error:
        await bot.send_message(user_id, error)
        return

    text = builder(data)
    await bot.send_message(user_id, text, reply_markup=get_nav_keyboard(token))

@router.callback_query(F.data.startswith("edit_note_"))
async def edit_note(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer()

    token = callback.data.replace("edit_note_", "")
    await state.set_state(CommentState.waiting_for_note)
    await state.set_data({"token": token})

    await bot.send_message(callback.from_user.id, "📝 Введите новый комментарий к серверу:")


@router.callback_query(F.data == "restart_ritual")
async def restart_ritual_choose_server(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

    user_id = callback.from_user.id
    servers = await get_servers(user_id)

    if not servers:
        await bot.send_message(user_id, "❌ У вас нет серверов.")
        return

    buttons = [
        [InlineKeyboardButton(text=f"{name or ip}", callback_data=f"restart_target_{token}")]
        for token, ip, name in servers
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.send_message(user_id, "🔁 Выберите сервер для перезапуска Ritual:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("restart_target_"))
async def restart_ritual_confirm(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()

    token = callback.data.replace("restart_target_", "")
    user_id = callback.from_user.id
    username = callback.from_user.username or "unknown"
    servers = await get_servers(user_id)
    server = next((s for s in servers if s[0] == token), None)

    if not server:
        await bot.send_message(user_id, "❌ Сервер не найден.")
        return

    ip = server[1]
    print(f"📣 Запрос перезапуска Ritual: user_id={user_id}, username=@{username}, ip={ip}")

    notice = await bot.send_message(user_id, "⏳ Перезапуск Ritual... Это может занять до 2 минут.")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://{ip}/restart_ritual",
                json={"token": token},
                timeout=180
            ) as resp:
                data = await resp.json()
    except Exception as e:
        await bot.delete_message(user_id, notice.message_id)
        await bot.send_message(user_id, f"❌ Ошибка: {e}")
        return

    await bot.delete_message(user_id, notice.message_id)

    if data.get("status") == "ok":
        await bot.send_message(user_id, f"✅ {data.get('message')}")
    else:
        await bot.send_message(user_id, f"⚠️ {data.get('message') or 'Перезапуск не удался'}")


@router.message(CommentState.waiting_for_note)
async def process_note_input(message: Message, state: FSMContext):
    data = await state.get_data()
    token = data.get("token")
    note = message.text.strip()

    await update_note(token, note)

    await message.answer("✅ Комментарий обновлён!")
    await state.clear()
