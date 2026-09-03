"""Pemantau pesanan Grab untuk GitHub Actions.

Dijalankan berkala oleh workflow. Tiap eksekusi:
  1. baca pesan baru di bot Telegram (link baru, /status, /stop),
  2. pantau semua pesanan aktif selama beberapa menit (polling tiap POLL detik),
  3. simpan state ke state.json agar eksekusi berikutnya melanjutkan.

Env wajib: TELEGRAM_BOT_TOKEN
Env opsional: RUN_SECONDS (default 240), POLL (default 30), NEAR_METERS (default 300)
"""

import json
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from grab_tracker import Telegram, extract_token, fetch, summarize, status_text  # noqa: E402

STATE_FILE = pathlib.Path(__file__).resolve().parent / "state.json"
RUN_SECONDS = int(os.getenv("RUN_SECONDS", "240"))
POLL = int(os.getenv("POLL", "30"))
NEAR = int(os.getenv("NEAR_METERS", "300"))

HELP = (
    "Kirim link lacak Grab (https://sharelocation.grab.com/o/XXXX) dan saya kabari "
    "tiap status berubah, ETA, dan saat driver sudah dekat.\n\n"
    "/status — pesanan yang sedang dipantau\n"
    "/stop — hentikan semua pemantauan"
)


def load() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"offset": 0, "orders": {}}


def save(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def read_messages(tg: Telegram, state: dict) -> None:
    tg.offset = state.get("offset", 0)
    res = tg.call("getUpdates", offset=tg.offset, timeout=0)
    if not res or not res.get("ok"):
        return
    for u in res["result"]:
        state["offset"] = u["update_id"] + 1
        msg = u.get("message") or u.get("edited_message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        text = (msg.get("text") or "").strip()
        if not chat_id or not text:
            continue

        if text.startswith(("/start", "/help")):
            tg.send(chat_id, HELP)
        elif text.startswith("/status"):
            if not state["orders"]:
                tg.send(chat_id, "Tidak ada pesanan yang sedang dipantau.")
            else:
                lines = []
                for tok in state["orders"]:
                    try:
                        lines.append(f"[{tok}]\n{status_text(summarize(fetch(tok)))}")
                    except Exception:  # noqa: BLE001
                        lines.append(f"[{tok}] gagal dibaca")
                tg.send(chat_id, "\n\n".join(lines))
        elif text.startswith("/stop"):
            arg = text[5:].strip()
            if arg and arg in state["orders"]:
                state["orders"].pop(arg)
                tg.send(chat_id, f"Pemantauan {arg} dihentikan.")
            elif state["orders"]:
                state["orders"].clear()
                tg.send(chat_id, "Semua pemantauan dihentikan.")
            else:
                tg.send(chat_id, "Tidak ada yang dipantau.")
        else:
            token = extract_token(text)
            if not token:
                tg.send(chat_id, "Link tidak dikenali.\n\n" + HELP)
            elif token in state["orders"]:
                tg.send(chat_id, f"Pesanan {token} sudah dipantau.")
            else:
                try:
                    s = summarize(fetch(token))
                except Exception as e:  # noqa: BLE001
                    tg.send(chat_id, f"Gagal membaca link itu ({e}). Pastikan link masih aktif.")
                    continue
                state["orders"][token] = {"chat": chat_id, "state": None, "headline": None, "near": False}
                tg.send(chat_id, f"🛵 Mulai memantau pesanan\n{status_text(s)}")


def poll_orders(tg: Telegram, state: dict) -> None:
    for token, info in list(state["orders"].items()):
        try:
            cur = summarize(fetch(token))
        except Exception as e:  # noqa: BLE001
            print(f"[{token}] gagal: {e}")
            continue

        if (cur["state"], cur["headline"]) != (info.get("state"), info.get("headline")):
            if info.get("state") is not None:
                tg.send(info["chat"], f"🛵 {cur.get('headline') or cur['state_label']}\n{status_text(cur)}")
            info["state"], info["headline"] = cur["state"], cur["headline"]

        if not info.get("near") and cur["distance_m"] is not None and cur["distance_m"] <= NEAR:
            tg.send(info["chat"], f"🛵 Driver sudah dekat!\nSekitar {cur['distance_m']} m dari lokasi kamu")
            info["near"] = True

        print(f"[{token}] {cur['state_label']} | ETA {cur['eta'] or '-'} | {cur['distance_m']} m", flush=True)

        if cur["finished"]:
            tg.send(info["chat"], f"🛵 Pemantauan selesai\n{cur['state_label']}")
            state["orders"].pop(token, None)


def main() -> None:
    tg = Telegram(os.environ["TELEGRAM_BOT_TOKEN"])
    state = load()
    read_messages(tg, state)

    deadline = time.time() + RUN_SECONDS
    while state["orders"] and time.time() < deadline:
        poll_orders(tg, state)
        if not state["orders"]:
            break
        time.sleep(POLL)
        read_messages(tg, state)

    save(state)
    print(f"selesai, {len(state['orders'])} pesanan masih dipantau")


if __name__ == "__main__":
    main()
