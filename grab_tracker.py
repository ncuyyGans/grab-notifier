"""Pemantau link share-location Grab + notifikasi Telegram.

Dua cara pakai:

1) Mode bot (disarankan) — tinggal kirim link Grab ke bot Telegram-mu:
       TELEGRAM_BOT_TOKEN=xxx python3 grab_tracker.py --bot
   Perintah bot: kirim link apa saja, /status, /stop [token], /help

2) Mode satu link langsung dari terminal:
       python3 grab_tracker.py "https://sharelocation.grab.com/o/TOKEN"
   Notifikasi Telegram aktif bila env TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID diisi.

Opsi umum: --interval 20 (detik), --port 8080 (dashboard web), --near 300 (meter),
--once (cetak status sekali lalu keluar).
"""

import argparse
import json
import math
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API = "https://api.grab.com/api/v1/safety/sharemyride/{token}/bookingdetails?fullData=true"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
LINK_RE = re.compile(r"(?:https?://\S*?/o/|^)([A-Za-z0-9_-]{10,})")

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


def extract_token(text: str) -> str | None:
    m = LINK_RE.search(text.strip())
    return m.group(1) if m else None


def fetch(token: str) -> dict:
    req = urllib.request.Request(API.format(token=token), headers={
        "User-Agent": UA,
        "Referer": "https://sharelocation.grab.com/",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


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
        data = urllib.parse.urlencode(params).encode()
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        try:
            with urllib.request.urlopen(url, data=data, timeout=70) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            print(f"[telegram {method} gagal] {e}")
            return None

    def send(self, chat_id, text: str) -> None:
        if chat_id:
            self.call("sendMessage", chat_id=chat_id, text=text)

    def updates(self):
        res = self.call("getUpdates", offset=self.offset, timeout=50)
        if not res or not res.get("ok"):
            time.sleep(3)
            return []
        out = res["result"]
        if out:
            self.offset = out[-1]["update_id"] + 1
        return out


class Tracker(threading.Thread):
    """Memantau satu token pesanan sampai selesai."""

    def __init__(self, token: str, tg: Telegram, chat_id, store: dict, interval: int, near: int):
        super().__init__(daemon=True)
        self.token, self.tg, self.chat_id = token, tg, chat_id
        self.store, self.interval, self.near = store, interval, near
        self.stopped = threading.Event()
        self.status: dict | None = None

    def notify(self, title: str, body: str = "") -> None:
        line = f"{title}\n{body}".strip()
        print(f">>> [{self.token}] {line}")
        self.store["events"].insert(0, {"t": datetime.now().strftime("%H:%M:%S"), "text": line})
        del self.store["events"][50:]
        self.tg.send(self.chat_id, f"🛵 {line}")

    def run(self) -> None:
        prev = None
        near_sent = False
        while not self.stopped.is_set():
            try:
                cur = summarize(fetch(self.token))
            except Exception as e:  # noqa: BLE001
                print(f"[{self.token}] gagal ambil data: {e}")
                self.stopped.wait(self.interval)
                continue

            self.status = cur
            self.store["orders"][self.token] = cur

            if prev is None:
                self.notify("Mulai memantau pesanan", status_text(cur))
            else:
                if (cur["state"], cur["headline"]) != (prev["state"], prev["headline"]):
                    self.notify(cur.get("headline") or cur["state_label"], status_text(cur))
                if not near_sent and cur["distance_m"] is not None and cur["distance_m"] <= self.near:
                    self.notify("Driver sudah dekat!", f"Sekitar {cur['distance_m']} m dari lokasi kamu")
                    near_sent = True

            print(f"[{cur['updated']}][{self.token}] {cur['state_label']} | ETA {cur['eta'] or '-'} | {cur['distance_m']} m", flush=True)

            if cur["finished"]:
                self.notify("Pemantauan selesai", cur["state_label"])
                break
            prev = cur
            self.stopped.wait(self.interval)
        self.store["orders"].pop(self.token, None)


HELP = (
    "Kirim link lacak Grab (mis. https://sharelocation.grab.com/o/XXXX) "
    "dan saya kabari tiap status berubah, ETA, dan saat driver sudah dekat.\n\n"
    "/status — status semua pesanan yang dipantau\n"
    "/stop — hentikan semua pemantauan\n"
    "/stop <token> — hentikan satu pesanan"
)


def run_bot(tg: Telegram, store: dict, interval: int, near: int, seed: str | None = None) -> None:
    trackers: dict[str, Tracker] = {}
    print("Bot Telegram aktif. Kirim link Grab ke bot.")
    seed_token = extract_token(seed) if seed else None
    if seed_token:
        t = Tracker(seed_token, tg, os.getenv("TELEGRAM_CHAT_ID"), store, interval, near)
        trackers[seed_token] = t
        t.start()
    while True:
        for u in tg.updates():
            msg = u.get("message") or u.get("edited_message") or {}
            chat_id = (msg.get("chat") or {}).get("id")
            text = (msg.get("text") or "").strip()
            if not chat_id or not text:
                continue

            for tok, t in list(trackers.items()):
                if not t.is_alive():
                    trackers.pop(tok, None)

            if text.startswith("/start") or text.startswith("/help"):
                tg.send(chat_id, HELP)
            elif text.startswith("/status"):
                if not trackers:
                    tg.send(chat_id, "Tidak ada pesanan yang sedang dipantau.")
                else:
                    tg.send(chat_id, "\n\n".join(
                        f"[{tok}]\n{status_text(t.status) if t.status else 'memuat…'}"
                        for tok, t in trackers.items()))
            elif text.startswith("/stop"):
                arg = text[5:].strip()
                targets = [arg] if arg in trackers else ([] if arg else list(trackers))
                if not targets:
                    tg.send(chat_id, "Tidak ada yang dihentikan (cek /status).")
                for tok in targets:
                    trackers.pop(tok).stopped.set()
                    tg.send(chat_id, f"Pemantauan {tok} dihentikan.")
            else:
                token = extract_token(text)
                if not token:
                    tg.send(chat_id, "Link tidak dikenali.\n\n" + HELP)
                    continue
                if token in trackers:
                    tg.send(chat_id, f"Pesanan {token} sudah dipantau.")
                    continue
                try:
                    fetch(token)
                except Exception as e:  # noqa: BLE001
                    tg.send(chat_id, f"Gagal membaca link itu ({e}). Pastikan link masih aktif.")
                    continue
                t = Tracker(token, tg, chat_id, store, interval, near)
                trackers[token] = t
                t.start()


PAGE = """<!doctype html><meta charset=utf-8><title>Lacak Pesanan Grab</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#0f1115;color:#eaeaea}
.wrap{max-width:560px;margin:0 auto;padding:18px}
.card{background:#181b21;border-radius:14px;padding:16px;margin-bottom:12px}
h1{font-size:18px;margin:0 0 12px}
.big{font-size:20px;font-weight:600;color:#00b140}
.k{color:#8b93a1;font-size:12px}
li{margin:6px 0;font-size:14px}
pre{white-space:pre-wrap;margin:6px 0 0;font:14px/1.5 system-ui}
</style>
<div class=wrap>
<h1>Lacak Pesanan Grab <span id=live class=k></span></h1>
<div id=orders></div>
<div class=card><span class=k>Riwayat notifikasi</span><ul id=events></ul></div>
</div>
<script>
let seen = 0;
async function tick(){
  try{
    const s = await (await fetch('/api')).json();
    const ks = Object.keys(s.orders);
    orders.innerHTML = ks.length ? ks.map(k=>{
      const t = s.orders[k];
      return `<div class=card><div class=big>${t.headline||t.state_label}</div>
        <div class=k>${k}</div><pre>${t.text}</pre></div>`;
    }).join('') : '<div class=card>Belum ada pesanan dipantau. Kirim link ke bot Telegram.</div>';
    live.textContent = 'update ' + new Date().toLocaleTimeString();
    events.innerHTML = s.events.map(e=>`<li><b>${e.t}</b> ${e.text.split('\\n')[0]}</li>`).join('');
    if(s.events.length > seen){
      if(seen && window.Notification && Notification.permission==='granted')
        new Notification('Pesanan Grab', {body: s.events[0].text});
      seen = s.events.length;
    }
  }catch(e){ live.textContent = 'koneksi terputus'; }
}
if(window.Notification && Notification.permission==='default') Notification.requestPermission();
tick(); setInterval(tick, 5000);
</script>
"""


def serve(store: dict, port: int) -> None:
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/api"):
                orders = {k: dict(v, text=status_text(v)) for k, v in store["orders"].items()}
                body = json.dumps({"orders": orders, "events": store["events"]}).encode()
                ctype = "application/json"
            else:
                body, ctype = PAGE.encode(), "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("link", nargs="?")
    ap.add_argument("--bot", action="store_true", help="mode bot Telegram (terima link lewat chat)")
    ap.add_argument("--interval", type=int, default=20)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--near", type=int, default=300)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    if args.once:
        token = extract_token(args.link or "")
        print(json.dumps(summarize(fetch(token)), indent=2, ensure_ascii=False))
        return

    store = {"orders": {}, "events": []}
    tg = Telegram(os.getenv("TELEGRAM_BOT_TOKEN"))
    threading.Thread(target=serve, args=(store, args.port), daemon=True).start()
    print(f"Dashboard: http://localhost:{args.port}")

    if args.bot:
        if not tg.token:
            raise SystemExit("Set TELEGRAM_BOT_TOKEN dulu untuk mode bot.")
        run_bot(tg, store, args.interval, args.near, args.link)
        return

    if not args.link:
        raise SystemExit("Beri link Grab, atau jalankan dengan --bot.")
    token = extract_token(args.link)
    if not token:
        raise SystemExit("Link tidak dikenali.")
    t = Tracker(token, tg, os.getenv("TELEGRAM_CHAT_ID"), store, args.interval, args.near)
    t.start()
    t.join()
    print("Sesi berakhir. Dashboard tetap hidup, Ctrl+C untuk keluar.")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
