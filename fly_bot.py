"""
Grab Notifier Bot untuk Fly.io
Bot Telegram pemantau pesanan Grab - 24/7 free hosting

Environment variables:
    TELEGRAM_BOT_TOKEN - Token dari @BotFather
    PORT - Port untuk web server (default: 8080)
"""

import json
import math
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configuration
API = "https://api.grab.com/api/v1/safety/sharemyride/{token}/bookingdetails?fullData=true"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
LINK_RE = re.compile(r"(?:https?://\S*?/o/|^)([A-Za-z0-9_-]{6,})")
NEAR_METERS = 300
DATA_DIR = Path("/data" if os.path.exists("/data") else ".")
ORDERS_FILE = DATA_DIR / "orders.json"

STATE_LABEL = {
    "ALLOCATING": "Mencari driver",
    "ORDER_CREATED": "Pesanan dibuat",
    "ORDER_ACCEPTED": "Pesanan diterima restoran",
    "ORDER_PREPARING": "Makanan sedang disiapkan",
    "ORDER_READY": "Makanan siap",
    "ORDER_EXECUTING": "Driver dalam perjalanan",
    "PICKING_UP": "Driver menuju restoran",
    "DROPPING_OFF": "Driver mengantar ke tujuan",
    "COMPLETED": "Pesanan selesai",
    "CANCELLED": "Pesanan dibatalkan",
}

HELP = (
    "Kirim link lacak Grab (mis. https://sharelocation.grab.com/o/XXXX) "
    "dan saya kabari tiap status berubah, ETA, dan saat driver sudah dekat.\n\n"
    "/status — status semua pesanan yang dipantau\n"
    "/stop — hentikan semua pemantauan\n"
    "/stop <token> — hentikan satu pesanan"
)

# In-memory storage
orders = {}  # token -> order info
trackers = {}  # token -> Tracker thread
lock = threading.Lock()


def load_orders():
    """Load orders from persistent storage"""
    global orders
    if ORDERS_FILE.exists():
        try:
            with open(ORDERS_FILE, 'r') as f:
                data = json.load(f)
                # Filter out expired orders (older than 6 hours)
                cutoff = time.time() - 6 * 3600
                orders = {k: v for k, v in data.items() if v.get('ts', 0) > cutoff}
                print(f"Loaded {len(orders)} orders from storage")
        except Exception as e:
            print(f"Error loading orders: {e}")
            orders = {}


def save_orders():
    """Save orders to persistent storage"""
    try:
        with lock:
            with open(ORDERS_FILE, 'w') as f:
                json.dump(orders, f)
    except Exception as e:
        print(f"Error saving orders: {e}")


def extract_token(text: str) -> str | None:
    m = LINK_RE.search(text.strip())
    return m.group(1) if m else None


def fetch(token: str) -> dict:
    headers = {
        "User-Agent": UA,
        "Referer": "https://sharelocation.grab.com/",
        "Accept": "application/json",
    }
    resp = requests.get(API.format(token=token), headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()


def haversine(a, b) -> float:
    if not a or not b:
        return float("inf")
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def summarize(d: dict) -> dict:
    booking = d.get("booking") or {}
    driver = d.get("driver") or {}
    msg = d.get("messageStatus") or {}
    route = d.get("route") or {}

    def loc(o):
        p = (o or {}).get("location") or {}
        if p.get("latitude") is None:
            return None
        return (p["latitude"], p["longitude"])

    dloc, dropoff = loc(driver), loc(booking.get("dropOff"))
    eta = route.get("ETA")
    eta_txt = None
    if eta:
        left = int(eta - time.time())
        eta_txt = f"{max(left, 0) // 60} menit lagi" if left > -600 else None

    dist = None if dloc is None or dropoff is None else round(haversine(dloc, dropoff))
    state = booking.get("bookingState") or ""
    return {
        "session": d.get("sessionStatus"),
        "state": state,
        "state_label": STATE_LABEL.get(state, state or "-"),
        "headline": msg.get("title"),
        "detail": ((msg.get("processMsg") or {}).get("message")),
        "driver": driver.get("name"),
        "vehicle": " ".join(x for x in [driver.get("vehicleModel"), driver.get("vehiclePlateNumber")] if x),
        "pickup": (booking.get("pickup") or {}).get("keywords"),
        "dropoff": (booking.get("dropOff") or {}).get("keywords"),
        "distance_m": dist if dist is not None and dist < 100000 else None,
        "eta": eta_txt,
        "updated": datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"),
        "finished": d.get("sessionStatus") not in (None, "ACTIVE") or state in ("COMPLETED", "CANCELLED"),
    }


def status_text(s: dict) -> str:
    parts = [s.get("headline") or s["state_label"]]
    if s.get("detail"):
        parts.append(s["detail"])
    parts.append(f"Status: {s['state_label']}")
    if s.get("eta"):
        parts.append(f"ETA: {s['eta']}")
    if s.get("distance_m") is not None:
        parts.append(f"Jarak ke tujuan: {s['distance_m']} m")
    if s.get("driver"):
        parts.append(f"Driver: {s['driver']} ({s.get('vehicle') or '-'})")
    if s.get("pickup"):
        parts.append(f"Dari: {s['pickup']}")
    return "\n".join(parts)


class Telegram:
    def __init__(self, token: str | None):
        self.token = token
        self.offset = 0

    def call(self, method: str, **params):
        if not self.token:
            return None
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        try:
            resp = requests.post(url, json=params, timeout=30)
            return resp.json()
        except Exception as e:
            print(f"[telegram {method} gagal] {e}")
            return None

    def send(self, chat_id, text: str) -> None:
        if chat_id and self.token:
            self.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML")

    def set_webhook(self, url: str) -> bool:
        """Set webhook for Telegram updates"""
        if not self.token:
            return False
        result = self.call("setWebhook", url=url, allowed_updates=["message", "edited_message"])
        print(f"Webhook set: {result}")
        return result.get("ok") if result else False


def send_notification(chat_id: int, title: str, body: str = ""):
    """Send notification to Telegram"""
    tg = Telegram(os.getenv("TELEGRAM_BOT_TOKEN"))
    line = f"{title}\n{body}".strip()
    print(f">>> [{chat_id}] {line}")
    tg.send(chat_id, f"🛵 {line}")


def track_order(token: str, chat_id: int):
    """Track a single order until completion"""
    tg = Telegram(os.getenv("TELEGRAM_BOT_TOKEN"))
    near_sent = False
    prev = None
    interval = 20  # seconds

    while True:
        try:
            cur = summarize(fetch(token))
        except Exception as e:
            print(f"[{token}] gagal ambil data: {e}")
            time.sleep(interval)
            continue

        # Update order info
        with lock:
            if token in orders:
                orders[token].update({
                    "status": cur,
                    "ts": time.time(),
                })
                save_orders()

        # First fetch
        if prev is None:
            send_notification(chat_id, "Mulai memantau pesanan", status_text(cur))
        else:
            # State changed
            if (cur["state"], cur["headline"]) != (prev["state"], prev["headline"]):
                send_notification(chat_id, cur.get("headline") or cur["state_label"], status_text(cur))
            # Driver near
            if not near_sent and cur["distance_m"] is not None and cur["distance_m"] <= NEAR_METERS:
                send_notification(chat_id, "Driver sudah dekat!", f"Sekitar {cur['distance_m']} m dari lokasi kamu")
                near_sent = True

        print(f"[{cur['updated']}][{token}] {cur['state_label']} | ETA {cur['eta'] or '-'} | {cur['distance_m']} m")

        # Check if finished
        if cur["finished"]:
            send_notification(chat_id, "Pemantauan selesai", cur["state_label"])
            with lock:
                orders.pop(token, None)
                save_orders()
            break

        prev = cur
        time.sleep(interval)

    with lock:
        trackers.pop(token, None)


def start_tracker(token: str, chat_id: int):
    """Start a tracker thread for an order"""
    with lock:
        if token in trackers:
            return False
        orders[token] = {"chat_id": chat_id, "ts": time.time(), "status": None}
        save_orders()
        t = threading.Thread(target=track_order, args=(token, chat_id), daemon=True)
        trackers[token] = t
        t.start()
        return True


def stop_tracker(token: str) -> bool:
    """Stop tracking an order"""
    with lock:
        if token in trackers:
            # Thread will exit on next iteration
            orders.pop(token, None)
            trackers.pop(token, None)
            save_orders()
            return True
        return False


# Flask routes
@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "orders": len(orders)})


@app.route("/")
def index():
    """Home page"""
    return jsonify({
        "service": "Grab Notifier Bot",
        "status": "running",
        "orders_tracking": len(orders),
        "orders": list(orders.keys())
    })


@app.route("/webhook", methods=["POST"])
def webhook():
    """Telegram webhook endpoint"""
    data = request.get_json()
    if not data:
        return "ok"

    msg = data.get("message") or data.get("edited_message")
    if not msg:
        return "ok"

    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()

    if not chat_id or not text:
        return "ok"

    tg = Telegram(os.getenv("TELEGRAM_BOT_TOKEN"))

    # Handle commands
    if text.startswith("/start") or text.startswith("/help"):
        tg.send(chat_id, HELP)
        return "ok"

    if text.startswith("/status"):
        with lock:
            if not orders:
                tg.send(chat_id, "Tidak ada pesanan yang sedang dipantau.")
            else:
                parts = []
                for tok, info in orders.items():
                    status = info.get("status")
                    if status:
                        parts.append(f"[{tok}]\n{status_text(status)}")
                    else:
                        parts.append(f"[{tok}] memuat…")
                tg.send(chat_id, "\n\n".join(parts))
        return "ok"

    if text.startswith("/stop"):
        arg = text[5:].strip()
        with lock:
            if arg and arg in orders:
                stop_tracker(arg)
                tg.send(chat_id, f"Pemantauan {arg} dihentikan.")
            elif not arg:
                # Stop all
                for tok in list(orders.keys()):
                    stop_tracker(tok)
                tg.send(chat_id, "Semua pemantauan dihentikan.")
            else:
                tg.send(chat_id, "Token tidak ditemukan.")
        return "ok"

    # Handle link
    token = extract_token(text)
    if not token:
        tg.send(chat_id, "Link tidak dikenali.\n\n" + HELP)
        return "ok"

    # Check if already tracking
    with lock:
        if token in orders:
            tg.send(chat_id, f"Pesanan {token} sudah dipantau.")
            return "ok"

    # Validate token by fetching once
    try:
        cur = summarize(fetch(token))
    except Exception as e:
        tg.send(chat_id, f"Gagal membaca link itu ({e}). Pastikan link masih aktif.")
        return "ok"

    # Start tracking
    if start_tracker(token, chat_id):
        tg.send(chat_id, f"🛵 Mulai memantau pesanan\n{status_text(cur)}")
    else:
        tg.send(chat_id, f"Pesanan {token} sudah dipantau.")

    return "ok"


def restore_trackers():
    """Restore trackers from saved orders on startup"""
    load_orders()
    for token, info in list(orders.items()):
        chat_id = info.get("chat_id")
        if chat_id:
            print(f"Restoring tracker for {token}")
            t = threading.Thread(target=track_order, args=(token, chat_id), daemon=True)
            trackers[token] = t
            t.start()


if __name__ == "__main__":
    # Restore any saved orders
    restore_trackers()

    # Set webhook if FLY_APP_NAME is set
    app_name = os.getenv("FLY_APP_NAME")
    if app_name:
        webhook_url = f"https://{app_name}.fly.dev/webhook"
        tg = Telegram(os.getenv("TELEGRAM_BOT_TOKEN"))
        tg.set_webhook(webhook_url)
        print(f"Webhook URL: {webhook_url}")

    port = int(os.getenv("PORT", 8080))
    print(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
