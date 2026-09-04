# Cara Disable Cloudflare Worker via Dashboard

## Langkah-langkah:

### 1. Login Cloudflare Dashboard
- Buka: https://dash.cloudflare.com
- Login dengan akun Anda

### 2. Akses Workers & Pages
- Klik menu "Workers & Pages" di sidebar kiri
- Atau langsung: https://dash.cloudflare.com/?to=/:account/workers-and-pages

### 3. Pilih Worker Bot
- Cari nama worker bot Telegram Anda (misal: "grab-notifier-bot" atau "grab-tracker")
- Klik nama worker tersebut

### 4. Hapus Cron Trigger
1. Di halaman worker, klik tab **"Triggers"** (biasanya ada di menu atas)
2. Cari trigger dengan schedule `* * * * *` (tiap menit)
3. Klik **ikon sampah** (🗑️) atau **"Delete"** di sebelah trigger tersebut
4. Konfirmasi penghapusan

### 5. Verifikasi
- Pastikan tidak ada trigger aktif lagi
- Worker tetap ada tapi tidak akan jalan otomatis

### 6. Update Webhook Telegram (Opsional tapi Recommended)

Setelah disable Cloudflare, webhook Telegram mungkin masih mengarah ke Cloudflare. Update ke Fly.io:

```bash
# Ganti <TOKEN> dengan token bot Telegram Anda
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://grab-notifier-bot.fly.dev/webhook"}'
```

Atau buka di browser:
```
https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://grab-notifier-bot.fly.dev/webhook
```

### 7. Cek Status Webhook
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

Pastikan response menunjukkan:
```json
{
  "ok": true,
  "result": {
    "url": "https://grab-notifier-bot.fly.dev/webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0
  }
}
```

## Selesai! ✅

Sekarang:
- ❌ Cloudflare Worker: **Disabled** (tidak aktif)
- ✅ Fly.io: **Running** (aktif 24/7)

Bot Telegram sekarang berjalan di Fly.io tanpa limit KV!

## Troubleshooting

### Tidak bisa akses Workers & Pages?
Pastikan Anda memilih domain/zone yang benar di dropdown atas.

### Tidak menemukan tab Triggers?
Coba klik "Settings" atau "Configuration" di worker tersebut.

### Webhook masih ke Cloudflare?
Pastikan Fly.io sudah deploy dan URL benar. Coba delete webhook dulu:
```bash
curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"
```
Lalu set ulang ke Fly.io.

## Gambaran Visual (Text)

```
Cloudflare Dashboard
├── Workers & Pages
│   └── grab-notifier-bot (klik)
│       ├── Overview
│       ├── [Triggers] ← KLIK INI
│       ├── Settings
│       └── ...
│
└── Triggers Page
    ├── Cron Triggers
    │   └── * * * * *  [🗑️ Delete] ← KLIK INI
    └── ...
```
