"""واجهة ويب صغيرة (مكتبة Python القياسية فقط) لمراقبة المدينة والموافقة على الطلبات من الموبايل.

python agentcity.py web                     # http://127.0.0.1:8787  (محلي فقط)
python agentcity.py web --host 0.0.0.0      # للموبايل على نفس الشبكة (أو عبر نفق آمن مثل Tailscale)

الأمان: كل شي بدو توكن (CITY_WEB_TOKEN أو توكن عشوائي محفوظ بـ city_home/web_token). أول فتح: /?t=TOKEN
وبعدها بينحفظ بكوكي HttpOnly/SameSite=Strict. كل POST بيتحقق من التوكن كمان (حماية CSRF).
الواجهة ما بتعدّل state.json مباشرة: القرارات بتروح لطابور store.enqueue وبيطبّقها المشغّل.
"""
import hmac, html, json, os, secrets, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from . import store

E = html.escape


def token():
    t = os.getenv("CITY_WEB_TOKEN")
    if t:
        return t
    p = store.path("web_token")
    if not os.path.exists(p):
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, secrets.token_urlsafe(24).encode())
        os.close(fd)
    return open(p).read().strip()


def apply_now():
    """إذا ما في مشغّل شغال، طبّق الطابور فوراً (عشان الموافقة تبين بالواجهة)."""
    if not store.runner_alive():
        from .city import City
        City()


def snapshot():
    st = store.load()
    audit = []
    if os.path.exists(store.path("audit.jsonl")):
        with open(store.path("audit.jsonl"), encoding="utf-8") as f:
            audit = [json.loads(l) for l in f.readlines()[-40:] if l.strip()]
    return {"stop": store.killed(), "runner": store.runner_alive(), "projects": list(st["projects"].values()),
            "approvals": [a for a in st["approvals"].values()], "agents": list(st["agents"]),
            "audit": audit[::-1]}


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--fg:#1b1f24;--mut:#66707a;--line:#e3e6ea;--ok:#1f8f4e;--bad:#c62f2f;--warn:#b26a00;--acc:#2f5fd0}
@media (prefers-color-scheme:dark){:root{--bg:#111418;--card:#1a1e24;--fg:#e8eaed;--mut:#9aa3ad;--line:#2b313a;--ok:#4cc27e;--bad:#ff6b6b;--warn:#f0a73a;--acc:#7aa2ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Tahoma,sans-serif}
main{max-width:860px;margin:0 auto;padding:16px}h1{font-size:20px;margin:4px 0 12px}h2{font-size:16px;margin:20px 0 8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin:8px 0}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.mut{color:var(--mut);font-size:13px}
.chip{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;border:1px solid var(--line)}
.done{color:var(--ok)}.failed,.blocked{color:var(--bad)}.running,.pending,.queued{color:var(--warn)}
button{font:inherit;border:0;border-radius:8px;padding:8px 14px;cursor:pointer;color:#fff;background:var(--acc)}
button.ok{background:var(--ok)}button.bad{background:var(--bad)}textarea{width:100%;min-height:90px;font:inherit;padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
.banner{background:var(--bad);color:#fff;padding:10px 12px;border-radius:10px}table{width:100%;border-collapse:collapse}td{padding:4px 6px;border-top:1px solid var(--line);vertical-align:top;font-size:13px}
code{font-size:12px;word-break:break-all}form{margin:0}
"""


def form(action, label, csrf, cls="", **fields):
    hid = "".join(f'<input type="hidden" name="{E(k)}" value="{E(str(v))}">' for k, v in fields.items())
    return (f'<form method="post" action="{action}">{hid}<input type="hidden" name="csrf" value="{E(csrf)}">'
            f'<button class="{cls}">{E(label)}</button></form>')


def page(s, csrf):
    out = []
    if s["stop"]:
        out.append(f'<div class="banner row">⛔ إيقاف الطوارئ مفعّل {form("/resume", "استئناف", csrf)}</div>')
    out.append(f'<div class="row mut">المشغّل: {"شغال" if s["runner"] else "متوقف"} · '
               f'<a href="/">تحديث</a> · <a href="/new">طلب جديد</a></div>')
    if not s["stop"]:
        out.append(f'<div class="row" style="margin-top:8px">{form("/stop", "⛔ إيقاف طوارئ", csrf, "bad")}</div>')
    pend = [a for a in s["approvals"] if a["status"] == "pending"]
    out.append(f"<h2>بانتظار موافقتك ({len(pend)})</h2>")
    for a in pend:
        out.append(f'<div class="card"><div><b>{E(a["action"])}</b> <span class="mut">{E(a["id"])} · {E(a["agent"])}@{E(a["project"])}</span></div>'
                   f'<code>{E(str(a["details"]))}</code><div class="row" style="margin-top:8px">'
                   f'{form("/decide", "موافقة", csrf, "ok", id=a["id"], ok=1)}{form("/decide", "رفض", csrf, "bad", id=a["id"], ok=0)}</div></div>')
    if not pend:
        out.append('<div class="mut">ما في شي.</div>')
    out.append("<h2>المشاريع</h2>")
    for P in sorted(s["projects"], key=lambda p: p["created"], reverse=True):
        rows = "".join(f'<tr><td>{E(t["id"])}</td><td class="{E(t["status"])}">{E(t["status"])}</td>'
                       f'<td>{E(t["agent"] or t["role"])}</td><td>{E(t["title"][:80])}</td></tr>' for t in P["tasks"])
        warn = "".join(f'<div style="color:var(--bad)">⚠️ {E(x)}</div>' for x in P.get("integrity", []))
        summ = f'<details><summary>التقرير</summary><div style="white-space:pre-wrap">{E(P["summary"])}</div></details>' if P["summary"] else ""
        out.append(f'<div class="card"><div class="row"><b>{E(P["id"])}</b><span class="chip {E(P["status"])}">{E(P["status"])}</span>'
                   f'<span class="mut">{P["tokens"]:,} توكن · ~${P.get("cost_usd", 0)}</span></div>'
                   f'<div>{E(P["request"][:200])}</div>{warn}<table>{rows}</table>{summ}</div>')
    if not s["projects"]:
        out.append('<div class="mut">ما في مشاريع.</div>')
    out.append("<h2>آخر الأحداث</h2><div class='card'><table>")
    for e in s["audit"][:25]:
        rest = {k: v for k, v in e.items() if k not in ("t", "event")}
        out.append(f'<tr><td class="mut" title="{E(e.get("t", ""))}">{E(e.get("t", "")[11:])}</td><td>{E(e.get("event", ""))}</td>'
                   f'<td><code dir="ltr" style="display:block;text-align:left">{E(json.dumps(rest, ensure_ascii=False)[:110])}</code></td></tr>')
    out.append("</table></div>")
    return "".join(out)


def shell(body, refresh=True):
    meta = '<meta http-equiv="refresh" content="10">' if refresh else ""
    return (f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">{meta}<title>Agent City</title>'
            f'<style>{CSS}</style></head><body><main><h1>🏙️ Agent City</h1>{body}</main></body></html>')


class H(BaseHTTPRequestHandler):
    TOKEN = ""

    def log_message(self, *a):
        pass

    def _authed(self, supplied=None):
        cand = supplied
        if cand is None:
            for c in self.headers.get("Cookie", "").split(";"):
                k, _, v = c.strip().partition("=")
                if k == "city_t":
                    cand = urllib.parse.unquote(v)
            cand = cand or self.headers.get("X-City-Token")
        return bool(cand) and hmac.compare_digest(cand, self.TOKEN)

    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=()):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _redirect(self, to="/", extra=()):
        self.send_response(303)
        self.send_header("Location", to)
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if "t" in q and self._authed(q["t"][0]):       # أول دخول بالتوكن: كوكي وبعدين نشيل التوكن من الرابط
            return self._redirect(u.path, [("Set-Cookie", f"city_t={urllib.parse.quote(self.TOKEN)}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000")])
        if not self._authed():
            return self._send(401, shell("<p>محتاج توكن. افتح الرابط اللي طبعته المدينة: <code>/?t=...</code></p>", False))
        csrf = self.TOKEN
        if u.path == "/":
            return self._send(200, shell(page(snapshot(), csrf)))
        if u.path == "/new":
            body = (f'<form method="post" action="/add"><input type="hidden" name="csrf" value="{E(csrf)}">'
                    '<p>طلب جديد للمدير:</p><textarea name="text" required></textarea>'
                    '<div class="row" style="margin-top:8px"><button>إرسال</button><a href="/">رجوع</a></div></form>')
            return self._send(200, shell(body, False))
        if u.path == "/api/state":
            return self._send(200, json.dumps(snapshot(), ensure_ascii=False), "application/json; charset=utf-8")
        return self._send(404, shell("<p>مش موجود</p>", False))

    def do_POST(self):
        n = min(int(self.headers.get("Content-Length") or 0), 100_000)
        f = {k: v[0] for k, v in urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace")).items()}
        if not (self._authed() and self._authed(f.get("csrf", ""))):
            return self._send(403, shell("<p>ممنوع</p>", False))
        path = urllib.parse.urlparse(self.path).path
        if path == "/decide" and f.get("id"):
            store.enqueue("decision", id=f["id"], ok=f.get("ok") == "1", via="web")
            apply_now()
        elif path == "/add" and f.get("text", "").strip():
            store.enqueue("request", text=f["text"].strip()[:20000], via="web")
            apply_now()
        elif path == "/stop":
            open(store.path("STOP"), "w").close()
            store.audit("stop", via="web")
        elif path == "/resume":
            if store.killed():
                os.remove(store.path("STOP"))
            store.audit("resume", via="web")
        else:
            return self._send(400, shell("<p>طلب غير صالح</p>", False))
        return self._redirect("/")


def make_server(host="127.0.0.1", port=8787):
    store.init()
    H.TOKEN = token()
    return ThreadingHTTPServer((host, port), H)


def serve(host="127.0.0.1", port=8787):
    srv = make_server(host, port)
    shown = "127.0.0.1" if host in ("0.0.0.0", "") else host
    print(f"واجهة المدينة: http://{shown}:{srv.server_address[1]}/?t={H.TOKEN}")
    if host not in ("127.0.0.1", "localhost"):
        print("تنبيه: HTTP بدون تشفير. للموبايل من برّا البيت استعمل نفق آمن (Tailscale/WireGuard/SSH)، مش port مفتوح عالإنترنت.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
