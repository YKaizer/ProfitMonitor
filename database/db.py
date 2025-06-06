import aiosqlite
from pathlib import Path

DB_PATH = Path("bot_data.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                user_id INTEGER,
                token TEXT,
                ip TEXT,
                name TEXT DEFAULT '',
                note TEXT DEFAULT '',
                alerts_enabled INTEGER DEFAULT 1
            )
        """)
        # попытка добавить колонку alerts_enabled если база создана ранее
        try:
            await db.execute("ALTER TABLE servers ADD COLUMN alerts_enabled INTEGER DEFAULT 1")
        except Exception:
            pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS token_history (
                token TEXT,
                ip TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # users — создаем без поля report_hour
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                notify_alerts INTEGER DEFAULT 0,
                daily_report INTEGER DEFAULT 0,
                report_hour INTEGER DEFAULT 10
            )
        """)
        await db.commit()


async def add_server(user_id: int, token: str, ip: str, name: str = "", alerts_enabled: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO servers (user_id, token, ip, name, alerts_enabled) VALUES (?, ?, ?, ?, ?)", (user_id, token, ip, name, alerts_enabled))
        await db.execute("INSERT INTO token_history (token, ip) VALUES (?, ?)", (token, ip))
        await db.commit()

async def get_servers(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT token, ip, name FROM servers WHERE user_id = ?", (user_id,))
        return await cursor.fetchall()

async def get_servers_extended(user_id: int):
    """Вернуть список серверов вместе с флагом alerts_enabled"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT token, ip, name, alerts_enabled FROM servers WHERE user_id = ?",
            (user_id,),
        )
        return await cursor.fetchall()

async def delete_server(user_id: int, token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM servers WHERE user_id = ? AND token = ?", (user_id, token))
        await db.commit()

async def get_user_by_token(token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, name, ip FROM servers WHERE token = ?", (token,))
        return await cursor.fetchone()  # возвращает кортеж или None

async def update_note(token: str, note: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE servers SET note = ? WHERE token = ?", (note, token))
        await db.commit()

async def get_note_and_name(token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name, note FROM servers WHERE token = ?", (token,))
        return await cursor.fetchone()  # (name, note)

async def get_user_settings(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT notify_alerts, daily_report FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            return {"notify_alerts": bool(row[0]), "daily_report": bool(row[1])}
        else:
            await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            await db.commit()
            return {"notify_alerts": True, "daily_report": False}

async def toggle_notify_alerts(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET notify_alerts = 1 - notify_alerts WHERE user_id = ?
        """, (user_id,))
        await db.commit()

async def toggle_daily_report(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET daily_report = 1 - daily_report WHERE user_id = ?
        """, (user_id,))
        await db.commit()

async def update_report_hour(user_id: int, hour: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET report_hour = ? WHERE user_id = ?", (hour, user_id))
        await db.commit()

async def get_report_hour(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT report_hour FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 10

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_notify_alerts_for_user(user_id: int) -> bool:
    async with aiosqlite.connect("bot_data.db") as db:
        async with db.execute("SELECT notify_alerts FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return False  # По умолчанию считаем True (или False — если хочешь отключать)
            return bool(row[0])

async def toggle_server_alert(user_id: int, token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE servers SET alerts_enabled = 1 - alerts_enabled WHERE user_id = ? AND token = ?",
            (user_id, token),
        )
        await db.commit()

async def get_server_alert_status(token: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT alerts_enabled FROM servers WHERE token = ?", (token,))
        row = await cursor.fetchone()
        return bool(row[0]) if row else False

async def get_ip(token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT ip FROM servers WHERE token = ?", (token,))
        row = await cursor.fetchone()
        return row[0] if row else None
