"""
Kaanlar Handyman — furniture fitting & handyman services, North London
========================================================================
Quote-request site (not a shop) — customer fills in the job details, Mehmet
gets emailed, and prices it up himself. No checkout, no automated pricing.

Environment variables to set in Render:
  RESEND_API_KEY   - Resend key, sends the quote-request emails
  NOTIFY_TO        - where quote requests go (defaults to andradudan4@gmail.com
                     for testing — change to bolukbasmobilya@gmail.com when live)
  RESEND_FROM      - the "from" address (defaults to the frontdesk.org.uk
                     sender already verified in Resend)
  SECRET_KEY       - Flask session secret (any random string)
"""

from flask import Flask, request, jsonify, render_template_string, session, Response
import os
import re
import uuid
import html
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-this-later")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
NOTIFY_TO = os.environ.get("NOTIFY_TO", "andradudan4@gmail.com")
RESEND_FROM = os.environ.get("RESEND_FROM", "Kaanlar Handyman Website <leads@frontdesk.org.uk>")

BRAND = "Kaanlar Handyman"
PHONE_DISPLAY = "07492 466 097"
PHONE_TEL = "+447492466097"
WHATSAPP_NUMBER = "447492466097"
EMAIL_ADDRESS = "bolukbasmobilya@gmail.com"

SERVICES = [
    ("🪑", "Furniture Assembly & Repair", "Flat-pack, wardrobes, beds, sofas — built properly and fixed when they're not."),
    ("🚪", "Window, Wall & Door Repairs", "Sticking doors, damaged frames, wall fixings — sorted without a fuss."),
    ("💡", "Minor Electrical Work", "Sockets, fittings and small electrical jobs done safely."),
    ("🎨", "Painting & Decorating", "Rooms, walls and woodwork finished neatly, no mess left behind."),
    ("🪵", "Flooring", "Laminate, vinyl and wood-effect flooring supplied and fitted."),
    ("🌧️", "Weatherproofing", "Sheds, fences and exteriors sealed up and protected."),
]

PRICING = [
    ("🔧", "Handyman", "£50", "General repairs, fixes and small jobs, per hour."),
    ("🪑", "Furniture Making & Fitting", "£60", "Flat-pack, wardrobes, beds and bespoke builds, per hour."),
]

GALLERY_COUNT = 27  # job-01.jpg .. job-27.jpg

NORTH_LONDON_AREAS = [
    "Enfield", "Barnet", "Haringey", "Islington", "Camden", "Hackney",
    "Waltham Forest", "Tottenham", "Wood Green", "Finchley", "Muswell Hill", "Southgate",
]


# --- Email (Resend) -----------------------------------------------------------

def _post_resend(subject, text, html_body=None):
    if not RESEND_API_KEY:
        print(f"RESEND_API_KEY not set, skipping email: {subject}")
        return
    payload = {"from": RESEND_FROM, "to": [NOTIFY_TO], "subject": subject, "text": text}
    if html_body:
        payload["html"] = html_body
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json=payload, timeout=15,
        )
        if r.status_code >= 300:
            print(f"Resend error: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Failed to send email: {e}")


def _row(label, value):
    if not value:
        return ""
    return (
        '<tr><td style="padding:10px 16px;border-bottom:1px solid #eee;color:#8a8a8a;'
        f'font-size:13px;white-space:nowrap;vertical-align:top;width:140px">{html.escape(label)}</td>'
        f'<td style="padding:10px 16px;border-bottom:1px solid #eee;color:#1a1a1a;'
        f'font-size:14px;font-weight:600">{html.escape(str(value))}</td></tr>'
    )


def _email_shell(title, inner):
    return (
        '<!DOCTYPE html><html><body style="margin:0;background:#f0f0ee;padding:24px;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif">'
        '<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;'
        'overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08)">'
        '<div style="background:#141516;padding:22px 28px">'
        '<div style="color:#FF5A1F;font-size:12px;letter-spacing:.18em;text-transform:uppercase;'
        'font-weight:800">Kaanlar Handyman</div>'
        f'<div style="color:#fff;font-size:20px;font-weight:800;margin-top:5px">{title}</div></div>'
        f'<div style="padding:24px 28px">{inner}</div>'
        '</div></body></html>'
    )


def send_quote_email(fields):
    text_lines = ["NEW QUOTE REQUEST - Kaanlar Handyman", "========================"]
    for k, v in fields.items():
        if v:
            text_lines.append(f"{k}: {v}")
    text_body = "\n".join(text_lines)

    rows = "".join(_row(k, v) for k, v in fields.items())
    inner = (
        '<p style="margin:0 0 20px;font-size:14px;color:#666">New quote request submitted via the website:</p>'
        f'<table style="width:100%;border-collapse:collapse;border:1px solid #eee;'
        f'border-radius:8px;overflow:hidden">{rows}</table>'
    )
    html_body = _email_shell("New quote request", inner)

    contact = fields.get("Phone") or fields.get("Email") or "no contact given"
    bits = [b for b in (fields.get("Name"), fields.get("Service")) if b]
    subject = "New quote request - " + (" · ".join(bits + [contact]) if bits else contact)
    _post_resend(subject, text_body, html_body=html_body)


def send_contact_email(name, email, message):
    inner = (
        f'<p style="margin:4px 0;font-size:14px"><strong>From:</strong> {html.escape(name)} ({html.escape(email)})</p>'
        f'<p style="margin:14px 0 0;font-size:14px;white-space:pre-wrap">{html.escape(message)}</p>'
    )
    _post_resend(f"Website message from {name}", message, _email_shell("New contact message", inner))


# --- Look & feel ----------------------------------------------------------------

BASE_STYLE = """
<meta name="theme-color" content="#111315">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Kaanlar Handyman">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root{
    --ink:#111315; --panel:#1b1e21; --panel-lt:#24282c; --mut:#a7adb3;
    --paper:#f5f4f1; --paper-ink:#16181a;
    --orange:#FF5A1F; --orange-dk:#c73e00; --orange-lt:#FF8A54;
    --yellow:#FFC93C;
    --line:rgba(255,255,255,.1);
  }
  *{box-sizing:border-box} html{scroll-behavior:smooth}
  body{margin:0;background:var(--ink);color:#f2f2f0;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1.6;-webkit-font-smoothing:antialiased}
  h1,h2,h3,.display{font-family:'Space Grotesk',sans-serif}
  a{color:var(--orange)} img,video{max-width:100%;display:block}
  .wrap{max-width:1160px;margin:0 auto;width:100%}.narrow{max-width:760px}
  nav{position:sticky;top:0;z-index:50;display:flex;align-items:center;justify-content:space-between;gap:18px;padding:14px 24px;background:rgba(17,19,21,.9);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
  .brand{display:flex;align-items:center;gap:10px;color:#fff;text-decoration:none;font-weight:700;letter-spacing:.02em;font-size:17px;font-family:'Space Grotesk',sans-serif}
  .brand .mark{width:38px;height:38px;border-radius:8px;background:linear-gradient(135deg,var(--orange),var(--yellow));display:flex;align-items:center;justify-content:center;font-weight:800;color:#141516;font-size:16px}
  .nav-actions{display:flex;align-items:center;gap:22px}
  .links{display:flex;align-items:center;gap:22px}.links a{color:#dcdcdc;text-decoration:none;font-size:13.5px;font-weight:600}.links a:hover{color:var(--orange)}
  .menu-toggle{display:none;background:none;border:0;font-size:22px;line-height:1;cursor:pointer;color:#fff;padding:4px}
  .mobile-menu{display:none;flex-direction:column;position:sticky;top:69px;z-index:49;background:var(--panel);border-bottom:1px solid var(--line)}
  .mobile-menu.open{display:flex}
  .mobile-menu a{padding:15px 24px;border-top:1px solid var(--line);text-decoration:none;color:#fff;font-weight:600;font-size:14.5px}
  .btn{display:inline-flex;align-items:center;gap:8px;justify-content:center;border:0;border-radius:999px;background:var(--orange);color:#141516;text-decoration:none;font-weight:800;padding:14px 26px;font-size:14.5px;cursor:pointer;box-shadow:0 10px 26px rgba(255,90,31,.28)}
  .btn:hover{background:var(--orange-lt)}
  .btn.ghost{background:transparent;border:1.5px solid #fff;color:#fff;box-shadow:none}
  .btn.wa{background:#25d366;color:#04220d;box-shadow:0 10px 26px rgba(37,211,102,.25)}
  .btn[disabled]{opacity:.5;cursor:not-allowed}
  .hero{position:relative;padding:0;display:grid;grid-template-columns:1.1fr .9fr;align-items:stretch;background:var(--ink);overflow:hidden;min-height:560px}
  .hero:before{content:"";position:absolute;inset:0;background:radial-gradient(900px 500px at 10% 10%,rgba(255,90,31,.22),transparent 60%);pointer-events:none}
  .hero-copy{padding:70px 56px;display:flex;flex-direction:column;justify-content:center;position:relative;z-index:1}
  .hero-copy .eyebrow{color:var(--yellow);font-size:12.5px;letter-spacing:.22em;text-transform:uppercase;font-weight:700}
  .hero-copy h1{font-size:clamp(34px,4.8vw,58px);line-height:1.04;margin:16px 0 18px;color:#fff;font-weight:700}
  .hero-copy h1 .hl{background:linear-gradient(120deg,var(--orange),var(--yellow));-webkit-background-clip:text;background-clip:text;color:transparent}
  .hero-copy p{font-size:17px;color:#cfd2d5;max-width:480px;margin:0 0 28px}
  .hero-img{position:relative;overflow:hidden}
  .hero-img img{width:100%;height:100%;object-fit:cover;min-height:340px;filter:saturate(1.05)}
  .hero-badge{position:absolute;left:24px;bottom:24px;background:rgba(17,19,21,.92);border:1px solid var(--line);border-radius:14px;padding:12px 16px}
  .hero-badge b{color:#fff;font-size:17px;display:block;font-family:'Space Grotesk',sans-serif}
  .hero-badge span{color:var(--mut);font-size:11.5px}
  .marquee{background:var(--panel);border-top:2px solid var(--orange);border-bottom:2px solid var(--orange);overflow:hidden}
  .marquee .track{display:inline-flex;white-space:nowrap;animation:mq 26s linear infinite;padding:13px 0}
  .marquee:hover .track{animation-play-state:paused}
  .marquee .grp{display:inline-flex;align-items:center;font-weight:700;font-size:12.5px;color:#fff;letter-spacing:.06em;text-transform:uppercase}
  .marquee .grp i{margin:0 20px;color:var(--yellow);font-style:normal}
  @keyframes mq{from{transform:translateX(0)}to{transform:translateX(-50%)}}
  .band{padding:78px 24px}
  .band.paper{background:var(--paper);color:var(--paper-ink)}
  .head{text-align:center;max-width:660px;margin:0 auto 42px}
  .head .eyebrow{color:var(--orange);font-size:12px;letter-spacing:.22em;text-transform:uppercase;font-weight:800}
  .head h2{font-size:clamp(28px,3.8vw,42px);margin:12px 0;font-weight:700}
  .head p{color:var(--mut);font-size:15.5px}
  .paper .head p{color:#63666a}
  .services{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}
  .scard{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:26px;transition:transform .2s,border-color .2s}
  .scard:hover{transform:translateY(-4px);border-color:var(--orange)}
  .scard .icon{font-size:28px;margin-bottom:14px}
  .scard h3{margin:0 0 8px;font-size:17px;color:#fff}
  .scard p{margin:0;color:var(--mut);font-size:14px}
  .pricing{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;max-width:620px;margin:0 auto}
  .pcard{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:30px 26px;text-align:center;transition:transform .2s,border-color .2s}
  .pcard:hover{transform:translateY(-4px);border-color:var(--orange)}
  .pcard .icon{font-size:26px;margin-bottom:10px}
  .pcard .rate{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:42px;color:var(--orange);line-height:1;margin:6px 0 2px}
  .pcard .rate span{font-family:Inter,sans-serif;font-size:14px;font-weight:600;color:var(--mut)}
  .pcard h3{margin:2px 0 8px;font-size:15px;color:#fff;text-transform:uppercase;letter-spacing:.04em}
  .pcard p{margin:0;color:var(--mut);font-size:13.5px}
  .pricing-note{text-align:center;color:var(--mut);font-size:13px;margin:22px 0 0}
  .paper .pricing-note{color:#63666a}
  .gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}
  .shot{position:relative;margin:0;border-radius:12px;overflow:hidden;background:#000;cursor:zoom-in;border:1px solid var(--line)}
  .shot img{width:100%;aspect-ratio:1/1;object-fit:cover;transition:transform .5s}
  .shot:hover img{transform:scale(1.07)}
  .about-grid{display:grid;grid-template-columns:.8fr 1.2fr;gap:50px;align-items:center}
  .about-photo{border-radius:16px;overflow:hidden;border:2px solid var(--orange);box-shadow:0 20px 50px rgba(0,0,0,.35);max-width:320px}
  .about-photo img{width:100%;aspect-ratio:3/4;object-fit:cover}
  .about-copy h3{font-size:15px}
  .badge-strip{display:flex;gap:12px;flex-wrap:wrap;margin-top:22px}
  .badge-strip span{background:var(--panel-lt);border:1px solid var(--line);border-radius:999px;padding:9px 16px;font-size:12.5px;font-weight:700;color:#fff}
  .cov-list{display:flex;flex-wrap:wrap;gap:9px;justify-content:center;margin-top:26px}
  .cov-list span{background:#fff;border:1px solid #e2e0da;border-radius:999px;padding:8px 15px;font-size:13px;font-weight:700;color:var(--paper-ink)}
  .quote-card{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:32px}
  .qgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-bottom:6px}
  .qgrid label{display:flex;flex-direction:column;gap:7px;font-size:12px;font-weight:700;letter-spacing:.04em;color:#c7cbce;text-transform:uppercase}
  .qgrid label.full{grid-column:1/-1}
  .qgrid input,.qgrid select,.qgrid textarea{font-family:inherit;font-size:15px;font-weight:500;color:#fff;background:rgba(255,255,255,.05);border:1px solid var(--line);border-radius:10px;padding:11px 13px;outline:none}
  .qgrid input:focus,.qgrid select:focus,.qgrid textarea:focus{border-color:var(--orange)}
  .qgrid textarea{resize:vertical;min-height:86px}
  .qgrid select option{color:#111}
  .qfoot{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-top:20px}
  .qmsg{margin-top:16px;font-size:14px;border-radius:10px;padding:12px 15px}
  .qmsg.ok{background:rgba(255,90,31,.14);border:1px solid rgba(255,90,31,.4);color:#ffd8c4}
  .qmsg.err{background:rgba(231,57,57,.12);border:1px solid rgba(231,57,57,.4);color:#f6c6c6}
  .qmsg a{color:#fff;font-weight:800;text-decoration:underline}
  .contact-box{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:28px}.contact-box p{margin:10px 0}
  .prose p{margin:0 0 16px;font-size:15.5px;color:#63666a}
  .prose h3{color:#fff;font-size:17px;margin:28px 0 8px}
  .paper .prose h3{color:var(--paper-ink)}
  .ctaband{background:linear-gradient(135deg,#1b1300,#141516);border:1px solid var(--line);border-radius:24px;padding:44px;text-align:center}
  .ctaband h2{font-size:clamp(24px,3.6vw,38px);margin:0 0 10px;color:#fff;font-weight:700}
  .ctaband p{color:var(--mut);margin:0 0 22px}
  footer{padding:48px 24px 30px;text-align:center;color:#8c9095;border-top:1px solid var(--line);background:#0c0d0e}
  footer .mark{width:40px;height:40px;border-radius:9px;background:linear-gradient(135deg,var(--orange),var(--yellow));display:flex;align-items:center;justify-content:center;font-weight:800;color:#141516;font-size:16px;margin:0 auto 14px}
  footer a{color:var(--orange-lt)}
  .wa-float{position:fixed;left:20px;bottom:22px;z-index:999998;width:58px;height:58px;border-radius:50%;background:#25d366;display:grid;place-items:center;box-shadow:0 12px 34px rgba(0,0,0,.4)}
  .wa-float svg{width:32px;height:32px;fill:#fff}
  .lb{position:fixed;inset:0;z-index:1000000;background:rgba(4,3,3,.94);display:none;align-items:center;justify-content:center;padding:24px;cursor:zoom-out}
  .lb.open{display:flex}.lb img{max-width:92vw;max-height:90vh;border-radius:12px;box-shadow:0 30px 90px rgba(0,0,0,.7)}
  .reveal{opacity:0;transform:translateY(18px);transition:opacity .7s ease,transform .7s ease}.reveal.in{opacity:1;transform:none}
  @media(max-width:860px){
    .hero{grid-template-columns:1fr}.hero-img{order:-1;height:240px}.hero-img img{min-height:0}.hero-copy{padding:36px 24px}
    .about-photo{max-width:220px;margin:0 auto 24px}
    .wa-float{display:none}
    .about-grid{grid-template-columns:1fr}
    .links{display:none}.menu-toggle{display:block}
    .band{padding:52px 18px}
  }

  /* cookie consent */
  .cc-bar{position:fixed;left:16px;right:16px;bottom:16px;z-index:999999;max-width:640px;margin:0 auto;
    background:rgba(17,19,21,.94);backdrop-filter:blur(8px);border:1px solid var(--line);
    border-radius:14px;padding:16px 18px;display:none;align-items:center;gap:16px;flex-wrap:wrap;
    box-shadow:0 20px 50px rgba(0,0,0,.4);transform:translateY(12px);opacity:0;transition:transform .35s ease,opacity .35s ease}
  .cc-bar.cc-show{display:flex}
  .cc-bar.cc-in{transform:translateY(0);opacity:1}
  .cc-bar p{margin:0;color:#eee;font-size:13.5px;line-height:1.5;flex:1 1 260px}
  .cc-bar a{color:var(--orange);text-decoration:underline}
  .cc-actions{display:flex;gap:10px;flex:0 0 auto}
  .cc-btn{font-family:inherit;font-size:13px;font-weight:700;padding:9px 16px;border-radius:999px;cursor:pointer;white-space:nowrap}
  .cc-accept{background:var(--orange);color:#141516;border:1px solid var(--orange)}
  .cc-reject{background:transparent;color:#eee;border:1.5px solid #fff}
  .cc-btn:focus-visible{outline:2px solid var(--orange);outline-offset:2px}
  @media(max-width:640px){.cc-bar{left:10px;right:10px;bottom:10px;padding:14px}.cc-actions{width:100%;justify-content:flex-end}}
  @media(prefers-reduced-motion:reduce){.cc-bar{transition:none}}
</style>
"""


def nav():
    return """
<nav>
  <a class="brand" href="/"><span class="mark">K</span><span>KAANLAR</span></a>
  <div class="nav-actions">
    <div class="links">
      <a href="/services">Services</a><a href="/gallery">Our Work</a><a href="/contact">Get a Quote</a>
    </div>
    <a class="btn" style="padding:10px 18px;font-size:13px" href="tel:""" + PHONE_TEL + """">Call""" + """</a>
    <button class="menu-toggle" onclick="document.getElementById('mobileMenu').classList.toggle('open')" aria-label="Menu">&#9776;</button>
  </div>
</nav>
<div class="mobile-menu" id="mobileMenu">
  <a href="/services">Services</a><a href="/gallery">Our Work</a><a href="/contact">Get a Quote</a>
</div>
"""


WA_SVG = '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 .4C7.4.4.5 7.3.5 15.9c0 2.8.7 5.4 2 7.8L.3 31.6l8.1-2.1c2.3 1.3 4.9 1.9 7.6 1.9 8.6 0 15.5-6.9 15.5-15.5S24.6.4 16 .4zm0 28.3c-2.4 0-4.7-.6-6.7-1.8l-.5-.3-4.8 1.3 1.3-4.7-.3-.5a12.7 12.7 0 0 1-2-6.8C3.2 8.8 8.9 3.2 16 3.2c7 0 12.7 5.7 12.7 12.7S23 28.7 16 28.7zm7-9.5c-.4-.2-2.3-1.1-2.6-1.3-.3-.1-.6-.2-.8.2-.2.4-.9 1.3-1.1 1.5-.2.2-.4.3-.8.1-.4-.2-1.6-.6-3.1-1.9-1.1-1-1.9-2.3-2.1-2.7-.2-.4 0-.6.2-.8l.6-.7c.2-.2.3-.4.4-.6.1-.2 0-.5 0-.7-.1-.2-.8-2-1.1-2.8-.3-.7-.6-.6-.8-.6h-.7c-.2 0-.6.1-1 .5-.3.4-1.3 1.3-1.3 3.1s1.3 3.6 1.5 3.9c.2.2 2.6 4 6.3 5.6.9.4 1.6.6 2.1.8.9.3 1.7.2 2.3.1.7-.1 2.3-.9 2.6-1.8.3-.9.3-1.6.2-1.8-.1-.1-.3-.2-.7-.4z"/></svg>'

MARQUEE_GRP = ('<span class="grp">North London &amp; Surrounding Areas <i>&bull;</i> Furniture Fitting <i>&bull;</i> '
               'Handyman Repairs <i>&bull;</i> Flooring &amp; Decorating <i>&bull;</i> 100% Satisfaction Guarantee <i>&bull;</i></span>')
MARQUEE = '<div class="marquee"><div class="track">' + MARQUEE_GRP + MARQUEE_GRP + '</div></div>'

SCRIPTS = """
<script>
(function(){
  var els=document.querySelectorAll('.reveal');
  if(!('IntersectionObserver' in window)){els.forEach(function(e){e.classList.add('in')});return;}
  var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}})},{threshold:.12});
  els.forEach(function(e){io.observe(e)});
})();
(function(){
  var lb=document.getElementById('lb'), img=document.getElementById('lbimg');
  if(!lb) return;
  document.querySelectorAll('.shot img').forEach(function(im){
    im.addEventListener('click',function(){ img.src=im.src; lb.classList.add('open'); });
  });
})();
async function submitQuote(ev){
  ev.preventDefault();
  var statusEl = document.getElementById('quoteStatus');
  if (document.getElementById('qWebsite').value.trim()) { return false; }
  var data = {
    name: document.getElementById('qName').value.trim(),
    phone: document.getElementById('qPhone').value.trim(),
    email: document.getElementById('qEmail').value.trim(),
    service: document.getElementById('qService').value,
    location: document.getElementById('qLocation').value.trim(),
    details: document.getElementById('qDetails').value.trim(),
  };
  if (!data.name || (!data.phone && !data.email)) {
    statusEl.className = 'qmsg err';
    statusEl.textContent = 'Please add your name and a phone number or email so Mehmet can send the quote back.';
    return false;
  }
  var btn = document.getElementById('quoteSubmit');
  btn.disabled = true; btn.textContent = 'Sending...';
  try {
    var r = await fetch('/quote', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data), credentials:'same-origin'});
    var d = await r.json();
    if (d.ok) {
      var waText = encodeURIComponent(
        'Hi Kaanlar Handyman, quote request:\\n' + 'Name: ' + data.name + '\\n' +
        (data.phone ? 'Phone: ' + data.phone + '\\n' : '') + (data.email ? 'Email: ' + data.email + '\\n' : '') +
        (data.service ? 'Service: ' + data.service + '\\n' : '') + (data.location ? 'Location: ' + data.location + '\\n' : '') +
        (data.details ? 'Details: ' + data.details : '')
      );
      statusEl.className = 'qmsg ok';
      statusEl.innerHTML = "Thanks " + (data.name.split(' ')[0] || '') + " - that's been sent over and Mehmet will get back to you with a price shortly. Prefer WhatsApp? <a href='https://wa.me/""" + WHATSAPP_NUMBER + """?text=' target='_blank' rel='noopener' id='waLink'>Send it on WhatsApp too</a>.";
      document.getElementById('waLink').href = 'https://wa.me/""" + WHATSAPP_NUMBER + """?text=' + waText;
      document.getElementById('quoteForm').reset();
    } else {
      statusEl.className = 'qmsg err'; statusEl.textContent = d.error || 'Something went wrong - please try again or call """ + PHONE_DISPLAY + """.';
    }
  } catch (e) {
    statusEl.className = 'qmsg err'; statusEl.textContent = 'Something went wrong - please try again or call """ + PHONE_DISPLAY + """.';
  }
  btn.disabled = false; btn.textContent = 'Get a Quote';
  return false;
}
(function(){
  var KEY = 'cookieConsent';
  var bar = document.getElementById('ccBar');
  if(!bar) return;
  var stored = null;
  try { stored = localStorage.getItem(KEY); } catch(e) {}
  if(stored !== 'accepted' && stored !== 'rejected'){
    bar.classList.add('cc-show');
    requestAnimationFrame(function(){ bar.classList.add('cc-in'); });
  }
  function hide(){
    bar.classList.remove('cc-in');
    setTimeout(function(){ bar.classList.remove('cc-show'); }, 350);
  }
  document.getElementById('ccAccept').addEventListener('click', function(){
    try { localStorage.setItem(KEY, 'accepted'); } catch(e) {}
    hide();
  });
  document.getElementById('ccReject').addEventListener('click', function(){
    try { localStorage.setItem(KEY, 'rejected'); } catch(e) {}
    hide();
  });
})();
</script>
"""

FOOTER = """
<section class="band"><div class="wrap"><div class="ctaband reveal">
  <h2>Got a job that needs doing?</h2>
  <p>Send the details and Mehmet will come back with a straight price.</p>
  <div style="display:flex;gap:14px;flex-wrap:wrap;justify-content:center">
    <a class="btn" href="tel:""" + PHONE_TEL + """">Call """ + PHONE_DISPLAY + """</a>
    <a class="btn wa" href="https://wa.me/""" + WHATSAPP_NUMBER + """" target="_blank" rel="noopener">WhatsApp</a>
  </div>
</div></div></section>
<footer>
  <div class="mark">K</div>
  <div style="color:#fff;font-weight:800;letter-spacing:.08em">KAANLAR HANDYMAN</div>
  <div style="margin-top:6px">Furniture Fitting &amp; Handyman Services &middot; North London</div>
  <div style="margin-top:12px"><a href="tel:""" + PHONE_TEL + """">""" + PHONE_DISPLAY + """</a> &nbsp;|&nbsp; <a href="mailto:""" + EMAIL_ADDRESS + """">""" + EMAIL_ADDRESS + """</a> &nbsp;|&nbsp; <a href="/privacy-policy">Privacy Policy</a> &nbsp;|&nbsp; <a href="/terms">Terms &amp; Conditions</a></div>
</footer>
<a class="wa-float" href="https://wa.me/""" + WHATSAPP_NUMBER + """" target="_blank" rel="noopener" aria-label="WhatsApp Kaanlar Handyman">""" + WA_SVG + """</a>
<div class="lb" id="lb" onclick="this.classList.remove('open')"><span></span><img id="lbimg" src="" alt=""></div>

<div class="cc-bar" id="ccBar" role="region" aria-label="Cookie notice">
  <p>This site uses a small number of essential cookies to keep it working properly. See our <a href="/privacy-policy">Privacy Policy</a> for details.</p>
  <div class="cc-actions">
    <button class="cc-btn cc-reject" id="ccReject" type="button">Reject</button>
    <button class="cc-btn cc-accept" id="ccAccept" type="button">Accept</button>
  </div>
</div>
"""


def page(title, body, description="Furniture fitting and handyman services across North London."):
    return render_template_string(
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>' + html.escape(title) + """ — Kaanlar Handyman</title>
<meta name="description" content=\"""" + html.escape(description) + """\">
<meta name="viewport" content="width=device-width, initial-scale=1">
""" + BASE_STYLE + """</head><body>""" + nav() + body + FOOTER + SCRIPTS + "</body></html>"
    )


QUOTE_FORM = """
<section class="band" id="quote"><div class="wrap narrow">
  <div class="head reveal"><div class="eyebrow">Get a Quote</div><h2>Tell Mehmet what needs doing.</h2><p>Fill this in and it lands straight in his inbox — he'll come back to you with a price, usually the same day.</p></div>
  <form class="quote-card reveal" id="quoteForm" onsubmit="return submitQuote(event)">
    <input type="text" id="qWebsite" autocomplete="off" tabindex="-1" style="position:absolute;left:-9999px;width:1px;height:1px;opacity:0" aria-hidden="true">
    <div class="qgrid">
      <label>Name<input type="text" id="qName" placeholder="Your name" required></label>
      <label>Phone<input type="tel" id="qPhone" placeholder="07..."></label>
      <label>Email<input type="email" id="qEmail" placeholder="you@example.com"></label>
      <label>Service<select id="qService">
        <option value="Furniture Assembly & Repair">Furniture Assembly &amp; Repair</option>
        <option value="Window, Wall & Door Repairs">Window, Wall &amp; Door Repairs</option>
        <option value="Minor Electrical Work">Minor Electrical Work</option>
        <option value="Painting & Decorating">Painting &amp; Decorating</option>
        <option value="Flooring">Flooring</option>
        <option value="Weatherproofing">Weatherproofing</option>
        <option value="Not sure yet">Not sure yet</option>
      </select></label>
      <label class="full">Area / Postcode<input type="text" id="qLocation" placeholder="e.g. Enfield, N21"></label>
      <label class="full">Job details<textarea id="qDetails" placeholder="What needs doing, roughly how big the job is"></textarea></label>
    </div>
    <div class="qfoot">
      <button class="btn" id="quoteSubmit" type="submit">Get a Quote</button>
      <span style="color:var(--mut);font-size:13px">No obligation — Mehmet only ever calls or messages back.</span>
    </div>
    <div id="quoteStatus"></div>
  </form>
</div></section>
"""


def pricing_section():
    pcards = "".join(
        f'<div class="pcard reveal"><div class="icon">{icon}</div><h3>{html.escape(name)}</h3>'
        f'<div class="rate">{rate}<span>/hr</span></div><p>{html.escape(desc)}</p></div>'
        for icon, name, rate, desc in PRICING
    )
    return """
<section class="band paper"><div class="wrap">
  <div class="head reveal"><div class="eyebrow">Pricing</div><h2>Straightforward hourly rates.</h2><p>Simple starting rates — final price depends on the job, confirmed before Mehmet starts.</p></div>
  <div class="pricing">""" + pcards + """</div>
  <p class="pricing-note">Bigger job? Send the details for a fixed quote.</p>
</div></section>
"""


def home_body():
    scards = "".join(
        f'<div class="scard reveal"><div class="icon">{icon}</div><h3>{html.escape(name)}</h3><p>{html.escape(desc)}</p></div>'
        for icon, name, desc in SERVICES
    )
    shots = "".join(
        f'<figure class="shot reveal"><img src="/static/images/gallery/job-{i:02d}.jpg" alt="Kaanlar Handyman completed job" loading="lazy"></figure>'
        for i in range(1, 9)
    )
    return """
<header class="hero">
  <div class="hero-copy">
    <div class="eyebrow">North London &middot; Fully Booked, Never Too Busy For You</div>
    <h1>Furniture fitting &amp;<br>handyman work, <span class="hl">done right.</span></h1>
    <p>Assembly, repairs, flooring, painting and more — built properly, fixed properly, every time. Send the details and get a straight price.</p>
    <div style="display:flex;gap:14px;flex-wrap:wrap">
      <a class="btn" href="/contact">Get a Quote</a>
      <a class="btn wa" href="https://wa.me/""" + WHATSAPP_NUMBER + """" target="_blank" rel="noopener">WhatsApp</a>
    </div>
  </div>
  <div class="hero-img">
    <img src="/static/images/action-wardrobe-fit.jpg" alt="Mehmet fitting a wardrobe">
    <div class="hero-badge"><b>100% Satisfaction</b><span>Guaranteed on every job</span></div>
  </div>
</header>
""" + MARQUEE + """

<section class="band"><div class="wrap">
  <div class="head reveal"><div class="eyebrow">Services</div><h2>Whatever needs fixing, fitting or building.</h2><p>Domestic jobs across North London, big or small.</p></div>
  <div class="services">""" + scards + """</div>
</div></section>
""" + pricing_section() + """
<section class="band paper"><div class="wrap about-grid">
  <div class="about-photo reveal"><img src="/static/images/headshot.jpg" alt="Mehmet Bolukbas, Kaanlar Handyman"></div>
  <div class="about-copy reveal">
    <div class="eyebrow" style="color:var(--orange)">Meet Mehmet</div>
    <h2 class="display" style="font-size:30px;margin:10px 0 16px">Hands-on, straight-talking, gets it done.</h2>
    <p style="color:#54575b;font-size:15.5px;margin:0 0 16px">Mehmet Bolukbas has been assembling, fitting and fixing across North London for years — from flat-pack wardrobes to full flooring installs. No subcontractors, no call centre — you deal with him directly, start to finish.</p>
    <div class="badge-strip">
      <span>&#11088; 100% Satisfaction Guarantee</span><span>&#128295; All Trades Covered</span><span>&#128205; North London Based</span>
    </div>
  </div>
</div></section>

<section class="band"><div class="wrap">
  <div class="head reveal"><div class="eyebrow">Our Work</div><h2>Real jobs, real photos.</h2><p>A few recent fits and fixes.</p></div>
  <div class="gallery reveal">""" + shots + """</div>
  <p style="text-align:center;margin-top:26px"><a href="/gallery">See the full gallery &rarr;</a></p>
</div></section>

<section class="band paper"><div class="wrap">
  <div class="head reveal"><div class="eyebrow">Coverage</div><h2>Based in North London.</h2><p>Covering these areas and nearby — not sure if that includes you? Just ask.</p></div>
  <div class="cov-list reveal">""" + "".join(f'<span>{a}</span>' for a in NORTH_LONDON_AREAS) + """</div>
</div></section>
""" + QUOTE_FORM


def services_body():
    scards = "".join(
        f'<div class="scard reveal"><div class="icon">{icon}</div><h3>{html.escape(name)}</h3><p>{html.escape(desc)}</p></div>'
        for icon, name, desc in SERVICES
    )
    return """
<section class="band"><div class="wrap">
  <div class="head reveal"><div class="eyebrow">Services</div><h2>All trades, one handyman.</h2><p>Domestic furniture fitting and handyman work across North London.</p></div>
  <div class="services">""" + scards + """</div>
</div></section>
""" + pricing_section() + """
""" + QUOTE_FORM


def gallery_body():
    shots = "".join(
        f'<figure class="shot reveal"><img src="/static/images/gallery/job-{i:02d}.jpg" alt="Kaanlar Handyman completed job" loading="lazy"></figure>'
        for i in range(1, GALLERY_COUNT + 1)
    )
    return """
<section class="band"><div class="wrap">
  <div class="head reveal"><div class="eyebrow">Our Work</div><h2>Recent jobs across North London.</h2><p>Tap any photo to view it full size.</p></div>
  <div class="gallery reveal">""" + shots + """</div>
</div></section>
""" + QUOTE_FORM


def contact_body(sent=False, error=None):
    if sent:
        inner = '<div class="msg qmsg ok">Thanks — your message is on its way to Mehmet. He\'ll reply as soon as he can.</div>'
    else:
        error_html = f'<div class="qmsg err">{html.escape(error)}</div>' if error else ""
        inner = """
    <form class="contact-form" method="post" action="/contact" style="display:grid;gap:16px;max-width:500px">
      <input type="text" name="website" autocomplete="off" tabindex="-1" style="position:absolute;left:-9999px" aria-hidden="true">
      <input type="text" name="name" placeholder="Your name" required style="padding:12px 14px;border-radius:8px;border:1px solid var(--line);background:rgba(255,255,255,.05);color:#fff">
      <input type="email" name="email" placeholder="Your email" required style="padding:12px 14px;border-radius:8px;border:1px solid var(--line);background:rgba(255,255,255,.05);color:#fff">
      <textarea name="message" placeholder="How can Mehmet help?" required style="padding:12px 14px;border-radius:8px;border:1px solid var(--line);background:rgba(255,255,255,.05);color:#fff;min-height:120px"></textarea>
      <button class="btn" type="submit">Send Message</button>
    </form>
    """ + error_html
    return """
<section class="band"><div class="wrap narrow">
  <div class="head reveal"><div class="eyebrow">Contact</div><h2>Get in touch</h2><p>Phone or WhatsApp is fastest — or use the quote form below.</p></div>
  <div class="contact-box reveal" style="margin-bottom:36px">
    <p><strong style="color:#fff">Phone:</strong> <a href="tel:""" + PHONE_TEL + """">""" + PHONE_DISPLAY + """</a></p>
    <p><strong style="color:#fff">Email:</strong> <a href="mailto:""" + EMAIL_ADDRESS + """">""" + EMAIL_ADDRESS + """</a></p>
    <p><strong style="color:#fff">WhatsApp:</strong> <a href="https://wa.me/""" + WHATSAPP_NUMBER + """" target="_blank" rel="noopener">Message Mehmet</a></p>
    <p><strong style="color:#fff">Area:</strong> North London and surrounding areas.</p>
  </div>
  """ + inner + """
</div></section>
""" + QUOTE_FORM


def privacy_body():
    return """
<section class="band"><div class="wrap narrow prose">
  <div class="head reveal"><div class="eyebrow">Legal</div><h2>Privacy Policy</h2><p>How Kaanlar Handyman handles the information you share through this website.</p></div>
  <div class="reveal">
    <p>This policy explains what information we collect when you use this website's quote form or contact form, why we collect it, and how it is kept.</p>
    <p>When you contact us we may collect your name, phone number, email address, and the details of the job you describe. We only collect what you choose to give us.</p>
    <p>We use this information for one purpose: to understand the job, reply to you, and provide a quote. We do not use it for marketing unless you ask us to.</p>
    <p>Enquiry details are sent to our own inbox so we can respond. To run the site we use trusted service providers — including an email provider to deliver enquiries — who process the information only to provide that service.</p>
    <p>You can ask us what information we hold about you, ask us to correct it, or ask us to delete it at any time. Get in touch using the details on the Contact page.</p>
  </div>
</div></section>
"""


def terms_body():
    return """
<section class="band"><div class="wrap narrow prose">
  <div class="head reveal"><div class="eyebrow">Legal</div><h2>Terms &amp; Conditions</h2><p>The terms that apply when you book a job with Kaanlar Handyman.</p></div>
  <div class="reveal">
    <p>These terms apply to any job booked with Kaanlar Handyman (Mehmet Bolukbas, &ldquo;we&rdquo;, &ldquo;us&rdquo;). By asking us to carry out work you agree to them.</p>
    <h3>Quotes</h3>
    <p>Prices given by phone, WhatsApp, email or the quote form are estimates based on what you've described. The final price is confirmed once we've seen the job or have all the details, and before any work starts.</p>
    <h3>Booking &amp; access</h3>
    <p>Please make sure someone is available at the property for the agreed time, with reasonable access to the work area.</p>
    <h3>Cancellations</h3>
    <p>We ask for as much notice as possible if a job needs to be moved or cancelled. Late cancellations, or access not being available on the day, may be subject to a reasonable charge.</p>
    <h3>Workmanship &amp; materials</h3>
    <p>Work is carried out to a professional standard using suitable materials. If anything about the finished job isn't right, let us know within a reasonable time and we'll come back and put it right.</p>
    <h3>Liability</h3>
    <p>We take care to protect your home and belongings while working. Our liability is limited to putting right work that falls below a reasonable standard.</p>
    <h3>Payment</h3>
    <p>Payment is due on completion unless otherwise agreed beforehand.</p>
    <h3>Website use</h3>
    <p>This website and its quote form are here to help you get a price quickly. Nothing on the site is a binding offer until Mehmet has confirmed a quote and a booking with you directly.</p>
    <h3>Governing law</h3>
    <p>These terms are governed by the law of England &amp; Wales.</p>
    <h3>Contact</h3>
    <p>Questions about these terms? Get in touch using the details on the Contact page.</p>
  </div>
</div></section>
"""


# --- Routes -----------------------------------------------------------------

@app.route("/")
def home():
    return page("Home", home_body(), "Furniture fitting and handyman services across North London — assembly, repairs, painting, flooring and more.")


@app.route("/services")
def services():
    return page("Services", services_body())


@app.route("/gallery")
def gallery():
    return page("Our Work", gallery_body())


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "GET":
        return page("Contact", contact_body())
    if (request.form.get("website") or "").strip():
        return page("Contact", contact_body(sent=True))
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip()
    message = (request.form.get("message") or "").strip()
    if not name or not email or not message:
        return page("Contact", contact_body(error="Please fill in every field."))
    send_contact_email(name, email, message)
    return page("Contact", contact_body(sent=True))


@app.route("/quote", methods=["POST"])
def quote_endpoint():
    data = request.get_json(silent=True) or {}
    if (data.get("website") or "").strip():
        return jsonify({"ok": True})

    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip()
    if not name or not (phone or email):
        return jsonify({"ok": False, "error": "Please add your name and a phone number or email."}), 400

    fields = {
        "Name": name,
        "Phone": phone or None,
        "Email": email or None,
        "Service": (data.get("service") or "").strip() or None,
        "Area / Postcode": (data.get("location") or "").strip() or None,
        "Job details": (data.get("details") or "").strip() or None,
    }
    send_quote_email(fields)
    return jsonify({"ok": True})


@app.route("/privacy")
@app.route("/privacy-policy")
def privacy():
    return page("Privacy Policy", privacy_body())


@app.route("/terms")
@app.route("/terms-and-conditions")
def terms():
    return page("Terms & Conditions", terms_body())


@app.route("/sitemap.xml")
def sitemap():
    pages = ["/", "/services", "/gallery", "/contact", "/privacy-policy", "/terms"]
    base = "https://kaanlarhandyman.co.uk"
    urls = "".join(f"<url><loc>{base}{p}</loc></url>" for p in pages)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>', mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    return Response("User-agent: *\nAllow: /\nSitemap: https://kaanlarhandyman.co.uk/sitemap.xml", mimetype="text/plain")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
