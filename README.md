# Pengingat Pesanan Grab lewat Telegram

Bot Telegram yang memantau link *share location* Grab (`https://sharelocation.grab.com/o/XXXX`)
dan mengirim notifikasi saat status pesanan berubah, ETA berubah, dan saat driver sudah dekat.
Berjalan gratis di GitHub Actions — tidak perlu laptop menyala, tidak perlu aplikasi Grab.

## Cara pakai (setelah terpasang)

Kirim ke bot Telegram-mu:

- link lacak Grab → bot mulai memantau pesanan itu
- `/status` → status semua pesanan yang dipantau
- `/stop` → hentikan pemantauan

## Pemasangan (semua lewat browser, tanpa install apa pun)

1. **Buat bot Telegram**: chat [@BotFather](https://t.me/BotFather) → `/newbot` → ikuti petunjuk →
   salin token yang diberikan (bentuknya `123456:ABC-DEF...`).
2. **Chat bot barumu** minimal satu kali (kirim "halo"), supaya bot boleh mengirim pesan ke kamu.
3. **Fork/salin repo ini** ke akun GitHub-mu.
4. Buka **Settings → Secrets and variables → Actions → New repository secret**:
   - Name: `TELEGRAM_BOT_TOKEN`
   - Secret: token dari BotFather
5. Buka tab **Actions** → aktifkan workflow (`I understand my workflows, go ahead and enable them`).
6. Selesai. Workflow jalan otomatis tiap 5 menit; saat ada pesanan aktif ia memantau tiap 30 detik.
   Untuk mencoba langsung: **Actions → Pantau pesanan Grab → Run workflow**.

> Catatan: cron GitHub kadang telat beberapa menit saat server sibuk. Kalau butuh lebih real-time,
> jalankan `python grab_tracker.py --bot` di komputer/VPS sendiri (polling terus-menerus).

## Menjalankan sendiri (opsional, di komputer sendiri)

```bash
set TELEGRAM_BOT_TOKEN=123456:ABC...      # Windows CMD
python grab_tracker.py --bot              # bot menerima link lewat chat
```

Dashboard web ringkas ikut aktif di <http://localhost:8080>.
Cek status satu link tanpa bot:

```bash
python grab_tracker.py "https://sharelocation.grab.com/o/XXXX" --once
```

## Isi repo

| File | Fungsi |
| --- | --- |
| `grab_tracker.py` | pustaka inti + bot mode (polling terus-menerus, dashboard web) |
| `track.py` | versi untuk GitHub Actions (jalan singkat lalu simpan `state.json`) |
| `state.json` | daftar pesanan yang sedang dipantau, ditulis otomatis oleh workflow |
| `.github/workflows/track.yml` | penjadwal tiap 5 menit |

Data diambil dari endpoint publik yang dipakai halaman share-location Grab
(`api.grab.com/api/v1/safety/sharemyride/<token>/bookingdetails`); tidak perlu login.
