# Panduan Migrasi: Cloudflare → Fly.io

## Apa yang terjadi jika Cloudflare Worker dibiarkan?

**Jawaban: Bot akan double-running!** ⚠️

Jika Cloudflare Worker dibiarkan aktif:
1. **Cron trigger masih jalan** → terus hit limit KV
2. **Webhook masih aktif** → bisa menerima update Telegram
3. **Bot jadi double** → Fly.io + Cloudflare berjalan bersamaan
4. **Notifikasi duplikat** → user dapat 2x pesan yang sama

## Langkah Migrasi yang Benar

### Step 1: Deploy Fly.io dulu
```bash
fly deploy
```

### Step 2: Update Webhook Telegram
Webhook otomatis di-set saat Fly.io deploy, tapi pastikan:
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

Pastikan URL mengarah ke `https://grab-notifier-bot.fly.dev/webhook`

### Step 3: Disable/Hapus Cloudflare Worker

**Opsi A: Disable Cron Trigger (Recommended)**
1. Login ke Cloudflare Dashboard
2. Pergi ke Workers & Pages → Your Worker
3. Tab "Triggers" → Delete cron trigger `* * * * *`
4. Worker tetap ada tapi tidak aktif

**Opsi B: Delete Worker (Clean)**
1. Login ke Cloudflare Dashboard
2. Workers & Pages → Your Worker
3. Settings → Delete Worker

**Opsi C: Via Wrangler CLI**
```bash
# Disable cron
wrangler trigger delete <worker-name>

# Atau delete worker
wrangler delete <worker-name>
```

### Step 4: Verifikasi

1. Kirim link Grab ke bot
2. Cek hanya 1 notifikasi yang masuk
3. Cek logs Fly.io: `fly logs`
4. Pastikan tidak ada error di Cloudflare

## Rollback (jika ada masalah)

Jika Fly.io bermasalah, bisa balik ke Cloudflare:

```bash
# Re-enable cron di Cloudflare Dashboard
# Atau via wrangler:
wrangler trigger create <worker-name> --cron "* * * * *"

# Update webhook balik ke Cloudflare
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://<worker>.workers.dev/tg"
```

## Checklist Migrasi

- [ ] Fly.io deployed dan running
- [ ] Webhook Telegram mengarah ke Fly.io
- [ ] Cloudflare cron trigger dihapus/disabled
- [ ] Test kirim link Grab → 1 notifikasi
- [ ] Test /status → response dari Fly.io
- [ ] Test /stop → berfungsi

## Troubleshooting

### Bot tidak responsif
```bash
# Cek Fly.io status
fly status
fly logs
```

### Double notifikasi
Pastikan webhook hanya mengarah ke 1 tempat:
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

Jika masih double, cek apakah Cloudflare worker masih aktif.

### Webhook error
```bash
# Reset webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/deleteWebhook"

# Set ulang ke Fly.io
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -d "url=https://grab-notifier-bot.fly.dev/webhook"
```

## Ringkasan

| Platform | Status | Action |
|----------|--------|--------|
| Fly.io | **Primary** | Deploy & aktifkan |
| Cloudflare | **Disable/Delete** | Hapus cron trigger atau delete worker |

**Rekomendasi**: Disable cron trigger di Cloudflare tapi jangan delete worker-nya dulu (jaga-jaga 1-2 hari), kalau Fly.io stabil baru delete Cloudflare Worker.
