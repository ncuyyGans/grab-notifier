# Alternatif Hosting Gratis 24/7 (Tanpa Credit Card)

Maaf, ternyata Railway juga sudah tidak free lagi (trial ended). Berikut alternatif lain yang **GRATIS dan TIDAK PERLU credit card**:

## 1. Render (Free Tier) ⭐ RECOMMENDED

**Keunggulan:**
- ✅ Tidak perlu credit card
- ✅ Free tier tersedia
- ✅ Deploy dari GitHub
- ✅ Support Docker

**Kekurangan:**
- ⚠️ Sleep setelah 15 menit idle (perlu keep-alive)

**Solusi:** Gunakan UptimeRobot (gratis) untuk ping tiap 5 menit

**Cara Deploy:**

### Step 1: Buat akun Render
1. https://render.com
2. Sign up dengan GitHub (tidak perlu CC)

### Step 2: New Web Service
1. Dashboard → "New" → "Web Service"
2. Connect GitHub repo

### Step 3: Konfigurasi
- **Name**: grab-notifier
- **Runtime**: Docker
- **Branch**: main
- **Environment Variables**:
  - `TELEGRAM_BOT_TOKEN` = token Anda
  - `PORT` = 8080

### Step 4: Deploy
Klik "Create Web Service"

### Step 5: Setup Keep Alive (PENTING!)

#### Opsi A: UptimeRobot (Recommended)
1. Buka https://uptimerobot.com
2. Sign up gratis
3. Add New Monitor:
   - Type: HTTP(s)
   - URL: `https://grab-notifier.onrender.com/health`
   - Interval: 5 minutes
4. Save

#### Opsi B: Cron-job.org
1. Buka https://cron-job.org
2. Create cron job:
   - URL: `https://grab-notifier.onrender.com/health`
   - Schedule: Every 5 minutes

### Step 6: Set Webhook Telegram
```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://grab-notifier.onrender.com/webhook"
```

**Selesai!** Bot berjalan 24/7 dengan keep-alive.

---

## 2. PythonAnywhere (Free Tier)

**Keunggulan:**
- ✅ Tidak perlu credit card
- ✅ Python native
- ✅ Always on (dengan task scheduled)
- ✅ Tidak sleep

**Kekurangan:**
- ⚠️ Hanya Python (tidak support Docker)
- ⚠️ Limited resources (512MB RAM)
- ⚠️ Domain PythonAnywhere (tidak custom)

**Cara Deploy:**

### Step 1: Buat akun
https://www.pythonanywhere.com

### Step 2: Upload files
1. Files → Upload `grab_tracker.py`
2. Files → Upload `requirements.txt`

### Step 3: Install dependencies
Open Bash console:
```bash
pip3 install --user flask requests
```

### Step 4: Create Flask app
Buat file `pythonanywhere_bot.py`:
```python
import os
import sys
sys.path.insert(0, '/home/YOUR_USERNAME/grab-notifier')

os.environ['TELEGRAM_BOT_TOKEN'] = 'YOUR_BOT_TOKEN'
os.environ['PORT'] = '8080'

from grab_tracker import main

if __name__ == "__main__":
    main()
```

### Step 5: Setup Web
1. Web → Add new web app
2. Choose "Manual configuration"
3. Python 3.11
4. Edit WSGI file, ganti dengan:
```python
import sys
path = '/home/YOUR_USERNAME/grab-notifier'
if path not in sys.path:
    sys.path.append(path)

from fly_bot import app as application
```

### Step 6: Set Environment Variables
Di Web tab, set:
- `TELEGRAM_BOT_TOKEN`

### Step 7: Reload web app

### Step 8: Set Webhook
```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://YOUR_USERNAME.pythonanywhere.com/webhook"
```

---

## 3. Replit + UptimeRobot

**Keunggulan:**
- ✅ Tidak perlu credit card
- ✅ Online IDE
- ✅ Free tier tersedia

**Kekurangan:**
- ⚠️ Sleep setelah 1 jam (perlu keep-alive)

**Cara:**
1. Import repo ke Replit (https://replit.com)
2. Set secret: `TELEGRAM_BOT_TOKEN`
3. Run bot
4. Gunakan UptimeRobot untuk ping tiap 5 menit ke URL Replit

---

## 4. Glitch + UptimeRobot

Sama seperti Replit, perlu keep-alive service.

---

## 5. Heroku (Free tier sudah tidak ada)

❌ Heroku sudah menghapus free tier sejak 2022

---

## 6. Oracle Cloud Free Tier (VPS)

**Keunggulan:**
- ✅ 2 VM ARM gratis selamanya
- ✅ 24/7 uptime
- ✅ Full VPS control

**Kekurangan:**
- ⚠️ Perlu setup manual
- ⚠️ Perlu CC untuk verifikasi (tapi tidak di-charge)

**Cara:**
1. https://www.oracle.com/cloud/free/
2. Sign up dengan CC (tidak di-charge)
3. Create VM instance
4. SSH ke VM
5. Install Python, deploy bot

---

## Rekomendasi Terbaik (No CC, Free):

| Platform | No CC | 24/7 | Setup | Notes |
|----------|-------|------|-------|-------|
| **Render + UptimeRobot** | ✅ | ✅* | Mudah | *Perlu keep-alive |
| **PythonAnywhere** | ✅ | ✅ | Medium | Limited resources |
| **Replit** | ✅ | ⚠️* | Mudah | *Perlu keep-alive |

## Langkah Cepat (Render - Recommended):

```bash
# 1. Push ke GitHub
git add .
git commit -m "Ready for Render"
git push origin main

# 2. Buka https://render.com
# 3. New → Web Service → Connect GitHub
# 4. Pilih repo, configure:
#    - Runtime: Docker
#    - Env: TELEGRAM_BOT_TOKEN
# 5. Deploy

# 6. Setup UptimeRobot:
#    - URL: https://grab-notifier.onrender.com/health
#    - Interval: 5 minutes

# 7. Set webhook:
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://grab-notifier.onrender.com/webhook"
```

## Perbandingan Platform:

| Platform | Credit Card | Free Tier | Uptime | Keep-alive |
|----------|-------------|-----------|--------|------------|
| Fly.io | ❌ Required | 3 VMs | 24/7 | No |
| Railway | ❌ Required | Trial ended | - | - |
| **Render** | ✅ No | Yes | 24/7* | Yes |
| **PythonAnywhere** | ✅ No | Yes | 24/7 | No |
| Replit | ✅ No | Yes | Sleep | Yes |
| Oracle Cloud | ⚠️ Verify | 2 VMs | 24/7 | No |

**Kesimpulan**: Render + UptimeRobot adalah solusi terbaik saat ini tanpa CC!
