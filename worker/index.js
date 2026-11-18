// Cloudflare Worker for the Kaanlar Handyman site.
// Pages are static files in public/. This handles the two forms that email Mehmet:
// POST /quote (the quote form, JSON) and POST /contact (the contact form).
// Same checks and email layout as app.py.

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;" }[c]));
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

function row(label, value) {
  if (!value) return "";
  return '<tr><td style="padding:10px 16px;border-bottom:1px solid #eee;color:#8a8a8a;' +
    `font-size:13px;white-space:nowrap;vertical-align:top;width:140px">${esc(label)}</td>` +
    '<td style="padding:10px 16px;border-bottom:1px solid #eee;color:#1a1a1a;' +
    `font-size:14px;font-weight:600">${esc(value)}</td></tr>`;
}

function shell(title, inner) {
  return '<!DOCTYPE html><html><body style="margin:0;background:#f0f0ee;padding:24px;' +
    'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif">' +
    '<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;' +
    'overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08)">' +
    '<div style="background:#141516;padding:22px 28px">' +
    '<div style="color:#FF5A1F;font-size:12px;letter-spacing:.18em;text-transform:uppercase;' +
    'font-weight:800">Kaanlar Handyman</div>' +
    `<div style="color:#fff;font-size:20px;font-weight:800;margin-top:5px">${title}</div></div>` +
    `<div style="padding:24px 28px">${inner}</div>` +
    '</div></body></html>';
}

async function send(env, subject, text, html, replyTo) {
  if (env.DRY_RUN === "1" || !env.RESEND_API_KEY) {
    console.log("DRY RUN email to", env.NOTIFY_TO, "|", subject);
    return;
  }
  const payload = { from: env.RESEND_FROM, to: [env.NOTIFY_TO], subject, text, html };
  if (replyTo) payload.reply_to = replyTo;
  const r = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { authorization: `Bearer ${env.RESEND_API_KEY}`, "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) console.log("Resend error:", r.status, await r.text());
}

async function limited(env, request) {
  if (!env.FORM_LIMIT) return false;
  const { success } = await env.FORM_LIMIT.limit({ key: request.headers.get("cf-connecting-ip") || "unknown" });
  return !success;
}

const str = (v) => (typeof v === "string" ? v.trim().slice(0, 3000) : "");
const looksLikeEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

async function quote(request, env) {
  if (await limited(env, request)) return json({ ok: false, error: "Please wait a moment before sending another request." }, 429);
  const data = await request.json().catch(() => ({}));
  if (str(data.website)) return json({ ok: true });
  const name = str(data.name), phone = str(data.phone), email = str(data.email);
  if (!name || !(phone || email)) return json({ ok: false, error: "Please add your name and a phone number or email." }, 400);

  const fields = {
    Name: name, Phone: phone, Email: email,
    Service: str(data.service), "Area / Postcode": str(data.location), "Job details": str(data.details),
  };
  const text = ["NEW QUOTE REQUEST - Kaanlar Handyman", "========================"];
  for (const [k, v] of Object.entries(fields)) if (v) text.push(`${k}: ${v}`);
  const rows = Object.entries(fields).map(([k, v]) => row(k, v)).join("");
  const html = shell("New quote request",
    '<p style="margin:0 0 20px;font-size:14px;color:#666">New quote request submitted via the website:</p>' +
    `<table style="width:100%;border-collapse:collapse;border:1px solid #eee;border-radius:8px;overflow:hidden">${rows}</table>`);
  const contact = phone || email || "no contact given";
  const bits = [name, fields.Service].filter(Boolean);
  await send(env, "New quote request - " + [...bits, contact].join(" · "), text.join("\n"), html, looksLikeEmail(email) ? email : null);
  return json({ ok: true });
}

async function contactPage(env, request, variant) {
  const res = await env.ASSETS.fetch(new URL(`/_contact/${variant}.html`, request.url));
  return new Response(res.body, { status: 200, headers: { "content-type": "text/html; charset=utf-8" } });
}

async function contact(request, env) {
  const form = await request.formData().catch(() => new FormData());
  if (str(form.get("website"))) return contactPage(env, request, "sent");
  if (await limited(env, request)) return contactPage(env, request, "busy");
  const name = str(form.get("name")), email = str(form.get("email")), message = str(form.get("message"));
  if (!name || !email || !message) return contactPage(env, request, "missing");
  const inner = `<p style="margin:4px 0;font-size:14px"><strong>From:</strong> ${esc(name)} (${esc(email)})</p>` +
    `<p style="margin:14px 0 0;font-size:14px;white-space:pre-wrap">${esc(message)}</p>`;
  await send(env, `Website message from ${name}`, message, shell("New contact message", inner), looksLikeEmail(email) ? email : null);
  return contactPage(env, request, "sent");
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
      // One address only: send www.<domain> to <domain>, as the Render version did.
      if (url.hostname.startsWith("www.")) {
        url.hostname = url.hostname.slice(4);
        return Response.redirect(url.toString(), 301);
      }
    if (request.method === "POST") {
      const origin = request.headers.get("origin");
      if (origin && new URL(origin).host !== url.host) return new Response("Forbidden", { status: 403 });
      if (url.pathname === "/quote") return quote(request, env);
      if (url.pathname === "/contact") return contact(request, env);
    }
    if (url.pathname.startsWith("/_contact")) return new Response("Not found", { status: 404 });
    return env.ASSETS.fetch(request);
  },
};
