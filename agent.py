from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import psutil, docker, subprocess, threading, time, requests, os, socket, sqlite3
from fastapi.responses import PlainTextResponse
import asyncio

app = FastAPI()
CHECK_INTERVAL = 60
ALERTS_ENABLED = False
ALERT_SENT = False
BOT_ALERT_URL = "http://91.108.246.138:8080/alert"
ALERT_DB_PATH = os.path.join(os.path.dirname(__file__), "alerts.db")
COMPOSE_PATH = os.path.expanduser("~/infernet-container-starter/deploy/docker-compose.yaml")
print("📁 Current working dir:", os.getcwd())
print("📄 Full DB path:", ALERT_DB_PATH)

# === Ноды ===
NODE_SYSTEMD = {
    "Cysic": "cysic.service",
    "Initverse": "initverse.service",
    "t3rn": "t3rn.service",
    "Pipe-Devnet": "pipe-node.service",
    "0G": "zgs.service",
    "Drosera": "drosera.service",  # ✅ Новая нода
    "Hyperspace": "aios.service"   # ✅ Новая нода
}

NODE_PROCESSES = {
    "Multiple": "multiple-node",
    "Dill Light Validator": "dill/light_node/data/beacondata",
    "Dill Full Validator": "dill/full_node/data/beacondata",
    "Gaia": "wasmedge",
    "Gensyn": "python -m hivemind_exp.gsm8k"
}
NODE_SCREENS = {
    "Gaia": "gaia_bot",
    "Dria": "dria_node"
}
NODE_DOCKER_CONTAINERS = {
    "Ritual": {"hello-world", "infernet-anvil", "infernet-fluentbit", "infernet-redis", "infernet-node"},
    "Biconomy": {"mee-node-deployment-node-1", "mee-node-deployment-redis-1"},
    "Unichain": {"unichain-node-op-node-1", "unichain-node-execution-client-1"},
    "Spheron": {"fizz-node"},
    "Pipe-Testnet": {"pipe"},
    "Waku": {
        "nwaku-compose-waku-frontend-1",
        "nwaku-compose-grafana-1",
        "nwaku-compose-prometheus-1",
        "nwaku-compose-postgres-exporter-1",
        "nwaku-compose-nwaku-1",
        "nwaku-compose-postgres-1"
    }  # ✅ Новая нода
}

NODE_DOCKER_IMAGES = {
    "Titan": "nezha123/titan-edge",
    "Aztec": "aztecprotocol/aztec"
}

# === Вспомогательные ===
def get_token():
    try:
        with open("token.txt") as f:
            return f.read().strip()
    except:
        return ""

def get_ip_address():
    return socket.gethostbyname(socket.gethostname())

# === SQLite ===
def init_alert_db():
    try:
        print("🛠 Создаю/проверяю базу данных...")
        with sqlite3.connect(ALERT_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    name TEXT PRIMARY KEY,
                    active INTEGER DEFAULT 0,
                    last_alert INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute("""
                INSERT OR IGNORE INTO settings (key, value) VALUES ('alerts_enabled', '1')
            """)
        print("✅ База данных и таблицы созданы.")
    except Exception as e:
        print(f"❌ Ошибка при инициализации БД: {e}")


def load_alerts_enabled():
    global ALERTS_ENABLED
    try:
        with sqlite3.connect(ALERT_DB_PATH) as conn:
            cursor = conn.execute("SELECT value FROM settings WHERE key = 'alerts_enabled'")
            row = cursor.fetchone()
            ALERTS_ENABLED = row and row[0] == '1'
    except:
        ALERTS_ENABLED = True

def save_alerts_enabled(flag: bool):
    with sqlite3.connect(ALERT_DB_PATH) as conn:
        conn.execute("""
            INSERT INTO settings (key, value)
            VALUES ('alerts_enabled', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, ('1' if flag else '0',))

def was_already_reported(name: str) -> bool:
    with sqlite3.connect(ALERT_DB_PATH) as conn:
        cur = conn.execute("SELECT active FROM alerts WHERE name = ?", (name,))
        row = cur.fetchone()
        return row and row[0] == 1

def mark_alert(name: str, status: bool):
    now = int(time.time())
    with sqlite3.connect(ALERT_DB_PATH) as conn:
        conn.execute("""
            INSERT INTO alerts (name, active, last_alert)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET active=excluded.active, last_alert=excluded.last_alert
        """, (name, int(status), now if status else 0))

# === Stats ===

def get_real_cpu_cores():
    try:
        return int(os.popen("nproc --all").read().strip())
    except Exception:
        return psutil.cpu_count()

def get_system_stats():
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "cpu_cores": get_real_cpu_cores(),
        "memory": {
            "percent": mem.percent,
            "used": mem.used,
            "total": mem.total
        },
        "disk": {
            "percent": disk.percent,
            "used": disk.used,
            "total": disk.total
        }
    }

def get_docker_status():
    try:
        client = docker.from_env()
        return {
            c.name: {
                "status": c.status,
                "started_at": c.attrs["State"]["StartedAt"]
            }
            for c in client.containers.list()
            if c.status == "running"
        }
    except Exception as e:
        return {"error": str(e)}

def get_systemd_services():
    statuses = {}
    for name in NODE_SYSTEMD.values():
        try:
            result = subprocess.check_output(["systemctl", "is-active", name], text=True).strip()
        except subprocess.CalledProcessError:
            result = "not found"
        statuses[name] = result
    return statuses

def get_background_processes():
    found = set()
    for proc in psutil.process_iter(['cmdline']):
        try:
            cmdline = proc.info.get('cmdline')
            if isinstance(cmdline, (list, tuple)):
                cmd = " ".join(cmdline)
            else:
                cmd = str(cmdline) if cmdline else ''
            for name, match in NODE_PROCESSES.items():
                if match in cmd:
                    found.add(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sorted(found)

def get_installed_nodes():
    result = []

    # 1. systemd
    for name, service in NODE_SYSTEMD.items():
        try:
            subprocess.check_output(["systemctl", "is-active", service], stderr=subprocess.DEVNULL)
            result.append(name)
        except subprocess.CalledProcessError:
            pass

    # 2. processes
    for proc in psutil.process_iter(['cmdline']):
        try:
            cmd = " ".join(proc.info['cmdline'])
            for name, keyword in NODE_PROCESSES.items():
                if keyword in cmd:
                    result.append(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # 3. screen
    try:
        screens = subprocess.check_output(["screen", "-ls"], text=True)
        for name, session in NODE_SCREENS.items():
            if session in screens:
                result.append(name)
    except:
        pass

    # 4. docker
    try:
        client = docker.from_env()
        containers = client.containers.list()
        names = {c.name for c in containers}
        images = [img for c in containers for img in c.image.tags if c.image.tags]

        for name, expected in NODE_DOCKER_CONTAINERS.items():
            if name == "Ritual":
                if len(expected & names) >= 3:
                    result.append(name)
            else:
                if expected.issubset(names):
                    result.append(name)

        for name, img_pattern in NODE_DOCKER_IMAGES.items():
            if any(img_pattern in img for img in images):
                result.append(name)
    except Exception as e:
        print("⚠️ Docker check failed:", e)

    return sorted(set(result))

# === Мониторинг ===
def send_alert(name: str, custom_message: str = None):
    try:
        payload = {
            "token": get_token(),
            "ip": get_ip_address(),
            "alert_id": f"{name}-{int(time.time())}",
            "message": custom_message or f"❌ Упала нода: {name}"
        }
        requests.post(BOT_ALERT_URL, json=payload)
        print(f"🔔 Алерт отправлен: {name}")
    except Exception as e:
        print("Ошибка отправки алерта:", e)

def monitor_nodes():
    print("🔍 Запускаю мониторинг нод...")
    installed_nodes = set(get_installed_nodes())
    print(f"🧩 Установленные ноды для мониторинга: {installed_nodes}")

    while True:
        failed = set()

        # === Systemd
        for name in installed_nodes:
            if name in NODE_SYSTEMD:
                service = NODE_SYSTEMD[name]
                try:
                    status = subprocess.check_output(["systemctl", "is-active", service], text=True).strip()
                    if status != "active":
                        failed.add(name)
                except subprocess.CalledProcessError:
                    failed.add(name)

        # === Docker
        try:
            client = docker.from_env()
            containers = client.containers.list()
            running = {c.name for c in containers}
            tags = [tag for c in containers for tag in c.image.tags if c.image.tags]

            for name in installed_nodes:
                if name in NODE_DOCKER_CONTAINERS:
                    expected = NODE_DOCKER_CONTAINERS[name]
                    if not expected.issubset(running):
                        failed.add(name)

                if name in NODE_DOCKER_IMAGES:
                    pattern = NODE_DOCKER_IMAGES[name]
                    if not any(pattern in tag for tag in tags):
                        failed.add(name)

        except Exception as e:
            print("⚠️ Docker check failed:", e)

        # === Процессы
        active = set()
        for p in psutil.process_iter(['cmdline']):
            try:
                cmd = " ".join(p.info['cmdline'])
                for proc_name, keyword in NODE_PROCESSES.items():
                    if proc_name in installed_nodes and keyword in cmd:
                        active.add(proc_name)
            except Exception:
                continue

        for name in installed_nodes:
            if name in NODE_PROCESSES and name not in active:
                failed.add(name)

        # === Screen-сессии
        try:
            screens = subprocess.check_output(["screen", "-ls"], text=True, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            screens = ""
        
        for name in installed_nodes:
            if name in NODE_SCREENS:
                session = NODE_SCREENS[name]
                if session not in screens:
                    failed.add(name)
        
        # === Особый случай: Gaia
        if "Gaia" in installed_nodes:
            if NODE_SCREENS["Gaia"] not in screens:
                failed.add("Gaia")


        # === Отправка алертов
        for name in failed:
            if ALERTS_ENABLED and not was_already_reported(name):
                send_alert(name)
                mark_alert(name, True)

        for name in installed_nodes:
            if name not in failed:
                mark_alert(name, False)

        time.sleep(CHECK_INTERVAL)

def monitor_disk():
    global ALERT_SENT
    while True:
        disk = psutil.disk_usage("/")
        percent = disk.percent

        # ⚠️ Проверка наличия ноды Ritual
        ritual_detected = False
        try:
            client = docker.from_env()
            containers = {c.name for c in client.containers.list()}
            ritual_containers = {"hello-world", "infernet-node", "infernet-anvil", "infernet-fluentbit", "infernet-redis"}
            ritual_detected = len(ritual_containers & containers) >= 3
        except Exception as e:
            print("Ошибка проверки Docker:", e)

        # 🔁 Перезапуск Ritual если диск > 80%
        if ritual_detected and percent > 80:
            try:
                print("📦 Диск > 80% и Ritual найден — перезапуск...")

                # Остановка docker-compose
                down_result = subprocess.call(["docker-compose", "-f", COMPOSE_PATH, "down"])

                time.sleep(80)
                # Завершение всех screen-сессий с именем 'ritual'
                subprocess.call("for s in $(screen -ls | grep ritual | awk '{print $1}'); do screen -S $s -X quit; done", shell=True)

                # Запуск docker-compose в новой screen-сессии
                up_result = subprocess.call(
                    ["screen", "-dmS", "ritual", "bash", "-c", f"docker-compose -f {COMPOSE_PATH} up"]
                )
                time.sleep(20)
                if down_result == 0 and up_result == 0:
                    print("✅ Ritual перезапущен успешно.")
                else:
                    print("⚠️ Перезапуск Ritual завершился с ошибками.")

            except Exception as e:
                print("❌ Ошибка перезапуска Ritual:", e)

        # 🔔 Алерт по диску
        if percent >= 80 and not ALERT_SENT:
            try:
                requests.post(BOT_ALERT_URL, json={
                    "token": get_token(),
                    "ip": get_ip_address(),
                    "percent": percent,
                    "alert_id": f"{get_ip_address()}-{int(time.time())}"
                })
                ALERT_SENT = True
            except Exception as e:
                print("Ошибка отправки алерта:", e)

        elif percent < 78 and ALERT_SENT:
            ALERT_SENT = False

        time.sleep(CHECK_INTERVAL)


# === Эндпоинты ===
@app.post("/ping")
async def ping(request: Request):
    data = await request.json()
    if data.get("token") != get_token():
        return JSONResponse(content={"error": "unauthorized"}, status_code=403)

    return {
        "system": get_system_stats(),
        "docker": get_docker_status(),
        "systemd": get_systemd_services(),
        "background": get_background_processes(),
        "nodes": get_installed_nodes()
    }

@app.post("/logs_services")
async def get_service_logs(request: Request):
    data = await request.json()
    if data.get("token") != get_token():
        return JSONResponse(content={"error": "unauthorized"}, status_code=403)

    service = data.get("service")
    if not service:
        return JSONResponse(content={"error": "missing service name"}, status_code=400)

    try:
        logs = subprocess.check_output(
            ["journalctl", "-u", service, "-n", "50", "--no-pager"],
            text=True
        )
        return PlainTextResponse(logs)
    except subprocess.CalledProcessError:
        return PlainTextResponse("⚠️ Не удалось получить логи", status_code=500)

@app.post("/update_token")
async def update_token(request: Request):
    data = await request.json()
    new_token = data.get("new_token")
    if not new_token:
        return {"status": "missing new_token"}
    with open("token.txt", "w") as f:
        f.write(new_token.strip())
    return {"status": "updated"}

@app.post("/nodes")
async def nodes_info(request: Request):
    data = await request.json()
    if data.get("token") != get_token():
        return JSONResponse(status_code=403, content={"error": "unauthorized"})

    nodes = get_installed_nodes()
    return {"nodes": nodes}

from fastapi.responses import PlainTextResponse

@app.post("/logs_docker")
async def get_docker_logs(request: Request):
    data = await request.json()
    if data.get("token") != get_token():
        return JSONResponse(content={"error": "unauthorized"}, status_code=403)

    container = data.get("container")
    if not container:
        return JSONResponse(content={"error": "missing container name"}, status_code=400)

    try:
        logs = subprocess.check_output(
            ["docker", "logs", "--tail", "50", container],
            text=True,
            stderr=subprocess.STDOUT
        )
        return PlainTextResponse(logs)
    except subprocess.CalledProcessError:
        return PlainTextResponse(f"⚠️ Не удалось получить логи контейнера `{container}`", status_code=500)

@app.post("/set_alert_mode")
async def set_alert_mode(request: Request):
    global ALERTS_ENABLED
    data = await request.json()
    enabled = data.get("enabled", True)
    ALERTS_ENABLED = bool(enabled)
    save_alerts_enabled(ALERTS_ENABLED)
    print(f"Уведомления об упавших нодах [FALL ALERTS MODE] updated: {'ENABLED ✅' if ALERTS_ENABLED else 'DISABLED ❌'}")
    return {"status": "ok", "alerts_enabled": ALERTS_ENABLED}

@app.post("/restart_ritual")
async def restart_ritual_endpoint(request: Request):
    data = await request.json()
    if data.get("token") != get_token():
        return JSONResponse(status_code=403, content={"error": "unauthorized"})

    try:
        # Проверка наличия Ritual
        client = docker.from_env()
        containers = {c.name for c in client.containers.list()}
        ritual_expected = {"hello-world", "infernet-node", "infernet-anvil", "infernet-fluentbit", "infernet-redis"}
        ritual_detected = len(ritual_expected & containers) >= 3

        if not ritual_detected:
            return {"status": "fail", "message": "⛔ На сервере не обнаружено ноды Ritual"}

        # Перезапуск Ritual
        down_result = subprocess.call(["docker-compose", "-f", COMPOSE_PATH, "down"])
        await asyncio.sleep(30)
        subprocess.call("for s in $(screen -ls | grep ritual | awk '{print $1}'); do screen -S $s -X quit; done", shell=True)
        up_result = subprocess.call(["screen", "-dmS", "ritual", "bash", "-c", f"docker-compose -f {COMPOSE_PATH} up"])
        await asyncio.sleep(20)
        if down_result == 0 and up_result == 0:
            return {"status": "ok", "message": "Ritual успешно перезапущен"}
        else:
            return {"status": "fail", "message": "Ошибка при перезапуске docker-compose"}

    except Exception as e:
        print("❌ Ошибка в /restart_ritual:", e)
        return JSONResponse(status_code=500, content={"status": "fail", "message": str(e)})

# === Запуск ===

@app.on_event("startup")
async def startup_event():
    init_alert_db()
    load_alerts_enabled()
    threading.Thread(target=monitor_nodes, daemon=True).start()
    threading.Thread(target=monitor_disk, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent:app", host="0.0.0.0", port=8844)
