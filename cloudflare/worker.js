/**
 * Bot Telegram pemantau pesanan Grab — Cloudflare Worker.
 *
 * Butuh:
 *   - Secret  BOT_TOKEN   (token dari @BotFather)
 *   - KV binding ORDERS   (namespace untuk menyimpan pesanan yang dipantau)
 *   - Cron trigger        (* * * * *  = tiap menit)
 *   - Webhook Telegram    https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<worker>.workers.dev/tg
 */

const API = (t) =>
  `https://api.grab.com/api/v1/safety/sharemyride/${t}/bookingdetails?fullData=true`;
const NEAR_METERS = 300;

const STATE_LABEL = {
  ALLOCATING: "Mencari driver",
  ORDER_CREATED: "Pesanan dibuat",
  ORDER_ACCEPTED: "Pesanan diterima restoran",
  ORDER_PREPARING: "Makanan sedang disiapkan",
  ORDER_READY: "Makanan siap",
  ORDER_EXECUTING: "Driver dalam perjalanan",
  PICKING_UP: "Driver menuju restoran",
  DROPPING_OFF: "Driver mengantar ke tujuan",
  COMPLETED: "Pesanan selesai",
  CANCELLED: "Pesanan dibatalkan",
};

const HELP =
  "Kirim link lacak Grab (https://sharelocation.grab.com/o/XXXX) dan saya kabari tiap status berubah, ETA, dan saat driver sudah dekat.\n\n" +
  "/status — pesanan yang sedang dipantau\n" +
  "/stop — hentikan semua pemantauan";

function extractToken(text) {
  const m = text.match(/(?:\/o\/|^)([A-Za-z0-9_-]{10,})/);
  return m ? m[1] : null;
}

function haversine(a, b) {
  if (!a || !b) return null;
  const R = 6371000, r = Math.PI / 180;
  const dLat = (b[0] - a[0]) * r, dLon = (b[1] - a[1]) * r;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLon / 2) ** 2;
  return Math.round(2 * R * Math.asin(Math.sqrt(h)));
}

async function fetchOrder(token) {
  const res = await fetch(API(token), {
    headers: { Referer: "https://sharelocation.grab.com/", Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function summarize(d) {
  const booking = d.booking || {};
  const driver = d.driver || {};
  const msg = d.messageStatus || {};
  const route = d.route || {};
  const loc = (o) => {
    const p = (o || {}).location || {};
    return p.latitude == null ? null : [p.latitude, p.longitude];
  };
  let dist = haversine(loc(driver), loc(booking.dropOff));
  if (dist != null && dist > 100000) dist = null;
  let eta = null;
  if (route.ETA) {
    const left = route.ETA - Math.floor(Date.now() / 1000);
    if (left > -600) eta = `${Math.max(left, 0) / 60 | 0} menit lagi`;
  }
  const state = booking.bookingState || "";
  return {
    state,
    label: STATE_LABEL[state] || state || "-",
    headline: msg.title || "",
    detail: (msg.processMsg || {}).message || "",
    driver: driver.name || "",
    vehicle: [driver.vehicleModel, driver.vehiclePlateNumber].filter(Boolean).join(" "),
    pickup: (booking.pickup || {}).keywords || "",
    dist,
    eta,
    finished:
      (d.sessionStatus && d.sessionStatus !== "ACTIVE") ||
      state === "COMPLETED" ||
      state === "CANCELLED",
  };
}

function statusText(s) {
  const out = [s.headline || s.label];
  if (s.detail) out.push(s.detail);
  out.push(`Status: ${s.label}`);
  if (s.eta) out.push(`ETA: ${s.eta}`);
  if (s.dist != null) out.push(`Jarak ke tujuan: ${s.dist} m`);
  if (s.driver) out.push(`Driver: ${s.driver} (${s.vehicle || "-"})`);
  if (s.pickup) out.push(`Dari: ${s.pickup}`);
  return out.join("\n");
}

async function send(env, chat, text) {
  await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chat, text }),
  });
}

async function listOrders(env) {
  const { keys } = await env.ORDERS.list({ prefix: "order:" });
  const out = [];
  for (const k of keys) {
    const v = await env.ORDERS.get(k.name, "json");
    if (v) out.push([k.name.slice(6), v]);
  }
  return out;
}

async function handleMessage(env, msg) {
  const chat = msg.chat && msg.chat.id;
  const text = (msg.text || "").trim();
  if (!chat || !text) return;

  if (text.startsWith("/start") || text.startsWith("/help")) {
    return send(env, chat, HELP);
  }
  if (text.startsWith("/status")) {
    const orders = await listOrders(env);
    if (!orders.length) return send(env, chat, "Tidak ada pesanan yang sedang dipantau.");
    const parts = [];
    for (const [tok] of orders) {
      try {
        parts.push(`[${tok}]\n${statusText(summarize(await fetchOrder(tok)))}`);
      } catch {
        parts.push(`[${tok}] gagal dibaca`);
      }
    }
    return send(env, chat, parts.join("\n\n"));
  }
  if (text.startsWith("/stop")) {
    const orders = await listOrders(env);
    if (!orders.length) return send(env, chat, "Tidak ada yang dipantau.");
    for (const [tok] of orders) await env.ORDERS.delete(`order:${tok}`);
    return send(env, chat, "Semua pemantauan dihentikan.");
  }

  const token = extractToken(text);
  if (!token) return send(env, chat, "Link tidak dikenali.\n\n" + HELP);
  if (await env.ORDERS.get(`order:${token}`)) {
    return send(env, chat, `Pesanan ${token} sudah dipantau.`);
  }
  let s;
  try {
    s = summarize(await fetchOrder(token));
  } catch (e) {
    return send(env, chat, `Gagal membaca link itu (${e.message}). Pastikan link masih aktif.`);
  }
  await env.ORDERS.put(
    `order:${token}`,
    JSON.stringify({ chat, state: s.state, headline: s.headline, near: false }),
    { expirationTtl: 60 * 60 * 6 },
  );
  return send(env, chat, `🛵 Mulai memantau pesanan\n${statusText(s)}`);
}

async function tick(env) {
  for (const [token, info] of await listOrders(env)) {
    let s;
    try {
      s = summarize(await fetchOrder(token));
    } catch {
      continue;
    }
    let changed = false;
    if (s.state !== info.state || s.headline !== info.headline) {
      await send(env, info.chat, `🛵 ${s.headline || s.label}\n${statusText(s)}`);
      info.state = s.state;
      info.headline = s.headline;
      changed = true;
    }
    if (!info.near && s.dist != null && s.dist <= NEAR_METERS) {
      await send(env, info.chat, `🛵 Driver sudah dekat!\nSekitar ${s.dist} m dari lokasi kamu`);
      info.near = true;
      changed = true;
    }
    if (s.finished) {
      await send(env, info.chat, `🛵 Pemantauan selesai\n${s.label}`);
      await env.ORDERS.delete(`order:${token}`);
    } else if (changed) {
      await env.ORDERS.put(`order:${token}`, JSON.stringify(info), { expirationTtl: 60 * 60 * 6 });
    }
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "POST" && url.pathname === "/tg") {
      const update = await request.json();
      const msg = update.message || update.edited_message;
      if (msg) await handleMessage(env, msg);
      return new Response("ok");
    }
    return new Response("grab notifier bot aktif");
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil(tick(env));
  },
};
