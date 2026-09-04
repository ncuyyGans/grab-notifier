# Grab Notifier Bot - Fly.io Deployment

Bot Telegram pemantau pesanan Grab yang berjalan 24/7 gratis di Fly.io (tanpa limit KV seperti Cloudflare).

## Keunggulan Fly.io vs Cloudflare Workers

| Fitur | Cloudflare Workers | Fly.io |
|-------|-------------------|--------|
| **Harga** | Free tier | Free tier (3 VMs) |
| **KV Limit** | 100k reads/hari | **Unlimited** |
| **Uptime** | 24/7 | **24/7 (tidak sleep)** |
| **Storage** | KV only | **Persistent disk** |
| **Cron** | Native | Threading dalam app |

## Prerequisites

1. Install Fly.io CLI:
```bash
curl -L https://fly.io/install.sh | sh
```

2. Login ke Fly.io:
```bash
fly auth login
```

3. Buat app baru:
```bash
fly apps create grab-notifier-bot
```

## Deployment

### 1. Set Environment Variables

```bash
fly secrets set TELEGRAM_BOT_TOKEN="your_bot_token_here"
```

### 2. Deploy

```bash
fly deploy
```

### 3. Set Webhook Telegram

Setelah deploy, webhook akan otomatis di-set. Atau manual:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://grab-notifier-bot.fly.dev/webhook"}'
```

## Penggunaan

Kirim link Grab ke bot Telegram:
```
https://sharelocation.grab.com/o/XXXXXXX
```

### Commands

- `/start` atau `/help` - Bantuan
- `/status` - Lihat semua pesanan yang dipantau
- `/stop` - Hentikan semua pemantauan
- `/stop <token>` - Hentikan satu pesanan

## Monitoring

- **Health Check**: `https://grab-notifier-bot.fly.dev/health`
- **Dashboard**: `https://grab-notifier-bot.fly.dev/`
- **Logs**: `fly logs`

## Update Bot

```bash
fly deploy
```

## Scale (jika perlu)

```bash
# Scale ke 2 machines
fly scale count 2

# Scale memory
fly scale memory 512
```

## Troubleshooting

### Cek logs
```bash
fly logs -a grab-notifier-bot
```

### Restart app
```bash
fly restart
```

### Cek status
```bash
fly status
```

## Struktur File

```
grab-notifier/
├── fly.toml              # Konfigurasi Fly.io
├── Dockerfile            # Container image
├── requirements.txt      # Python dependencies
├── fly_bot.py           # Main application
└── README_FLYIO.md      # Dokumentasi ini
```

## Perbedaan dengan Cloudflare Worker

| Aspek | Cloudflare | Fly.io |
|-------|-----------|--------|
| **Storage** | KV (key-value) | File JSON persistent |
| **Cron** | Native cron trigger | Python threading |
| **Runtime** | V8 isolates | Docker container |
| **Cold start** | ~0ms | ~1-2 detik |
| **Memory** | 128MB | 256MB (bisa scale) |

## Catatan Penting

1. **Free tier Fly.io**: 3 shared-cpu-1x VMs gratis selamanya
2. **Persistent storage**: Data tersimpan di `/data/orders.json`
3. **Auto-restart**: Jika app crash, Fly.io otomatis restart
4. **Region**: Default Singapore (sin) - terdekat dengan Indonesia

## Support

Jika ada masalah, cek:
- Fly.io status: https://status.fly.io
- Telegram Bot API: https://core.telegram.org/bots/api
