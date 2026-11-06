"""اختبارات التحسينات: Docker sandbox، قواعد مخاطر/بروتوكول أشد، مراقبة final_test.lock، طابور القرارات، واجهة الويب."""
import http.cookiejar, json, os, sys, tempfile, threading, urllib.error, urllib.parse, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["CITY_HOME"] = tempfile.mkdtemp()
import numpy as np, pandas as pd
from city import sandbox, store, tools
from city.city import City

store.init()
sys.path.insert(0, store.path("workspace", "shared"))
from gold_toolkit import backtest, protocol, risk, strategies

c = City()
pid = c.add_request("improvements test")
P = c.st["projects"][pid]
T = {"id": "t1"}
ctx = tools.Ctx(c.st, P, T, "engineer")

# ---------- 1) sandbox ----------
_, cmd = sandbox.command(["python", "/work/x.py"], ctx.workdir, store.path("workspace", "shared"))
j = " ".join(cmd)
for flag in ("--network none", "--read-only", "--cap-drop ALL", "no-new-privileges", "--pids-limit",
             ":/shared:ro", ":/work:rw", "--memory"):
    assert flag in j, flag
assert "ANTHROPIC" not in j
if sandbox.available():
    code = ("import os,socket\n"
            "try: open('/shared/gold_toolkit/risk.py','a').write('x'); print('RISK_WRITABLE')\n"
            "except OSError: print('risk ro')\n"
            "try: socket.create_connection(('pypi.org',443),timeout=3); print('NET_OPEN')\n"
            "except OSError: print('net blocked')\n"
            "from gold_toolkit import risk; print('uid', os.getuid(), 'dd', risk.MAX_DD)\n")
    out = tools.run_python(ctx, {"code": code})
    assert "risk ro" in out and "net blocked" in out and "uid 0" not in out, out
    old = tools.TIMEOUT; tools.TIMEOUT = 3
    assert "timeout" in tools.run_python(ctx, {"code": "import time; time.sleep(60)"})
    tools.TIMEOUT = old
    print("  (docker sandbox integration checked)")
else:
    print("  (docker not available: integration part skipped)")
# وضع docker إجباري بدون صورة = رفض، مش تشغيل محلي
os.environ["CITY_SANDBOX"], img = "docker", sandbox.IMAGE
sandbox.IMAGE = "agentcity-sandbox:does-not-exist"; sandbox.available(refresh=True)
try:
    tools.run_python(ctx, {"code": "print(1)"}); raise SystemExit("strict sandbox ran locally!")
except RuntimeError:
    pass
os.environ["CITY_SANDBOX"] = "local"
assert "exit=0" in tools.run_python(ctx, {"code": "print(1)"})
sandbox.IMAGE = img; os.environ["CITY_SANDBOX"] = "auto"; sandbox.available(refresh=True)
try:
    tools.run_python(ctx, {"path": "../p999/x.py"}); raise SystemExit("ran file outside project")
except PermissionError:
    pass

# ---------- 2) قواعد المخاطر والبروتوكول ----------
m = lambda **k: dict({"return": .1, "sharpe": 1.0, "max_dd": -.1, "trades": 12, "buy_hold": .1,
                      "bh_sharpe": .5, "bh_max_dd": -.2}, **k)
assert risk.check({"train": m(), "val": m(sharpe=0.9)})["passed"]
r = risk.check({"train": m(), "val": m(sharpe=0.9, trades=2)})
assert not r["passed"] and any("التحقق" in x and "صفقات" in x for x in r["reasons"])
assert not risk.check({"train": m(), "val": m(sharpe=0.6, bh_sharpe=0.8)})["passed"], "must beat buy & hold"
v = m(); v.pop("bh_sharpe")
assert not risk.check({"train": m(), "val": v})["passed"], "missing benchmark must fail closed"
assert risk.final_check(m())["passed"]
assert not risk.final_check(m(trades=1))["passed"]
assert not risk.final_check(m(sharpe=0.11, bh_sharpe=1.12))["passed"], "the +1.3% vs +74.7% case must fail now"
assert risk.MAX_DD == 0.30 and risk.MIN_TRADES == 10 and risk.MIN_VAL_SHARPE == 0.3, "old rules not loosened"

rng = np.random.default_rng(1)
close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, .01, 2000))), index=pd.bdate_range("2015-01-01", periods=2000))
e = backtest.evaluate(close, pd.Series(1.0, index=close.index), 0, 500)
assert abs(e["sharpe"] - e["bh_sharpe"]) < 0.05, e        # always-long ~= benchmark
lockdir = tempfile.mkdtemp()
pr = protocol.Protocol(close, lock_dir=lockdir)
never = pd.Series(0.0, index=close.index)
try:
    pr.open_final("flat", {}, never); raise SystemExit("opened final for failing strategy")
except protocol.FinalTestError as ex:
    assert "risk.check" in str(ex)
assert not pr.final_opened()
pr.check = lambda pos: {"passed": True, "reasons": []}       # نفترض نجح، لنختبر القفل
rec = pr.open_final("s", {"a": 1}, never)
assert rec["test"]["trades"] == 0 and pr.final_opened()
try:
    pr.open_final("s", {"a": 1}, never); raise SystemExit("final opened twice")
except protocol.FinalTestError as ex:
    assert "already opened" in str(ex)
for t in ("rsi_reversion", "breakout"):
    pine = strategies.pine_fallback(strategies.random_candidates(1)[0] | {"template": t, "params":
                                    {"period": 20, "low": 40, "high": 70} if t == "rsi_reversion" else {"entry": 20, "exit": 10}})
    assert "var bool inPos = false" in pine and "not inPos" in pine, t

# ---------- 3) مراقبة final_test.lock ----------
lock = store.path("workspace", pid, "final_test.lock")
open(lock, "w").write('{"strategy":"x"}')
c.watch_final_lock(P)
assert P.get("final_lock") and not P.get("integrity")
os.remove(lock)
c.watch_final_lock(P)
assert P["integrity"] and "deleted" in P["integrity"][0]
open(lock, "w").write('{"strategy":"y"}')
c.watch_final_lock(P)
assert len(P["integrity"]) == 2 and "modified" in P["integrity"][1]
c.save()

# ---------- 4) الطابور + قفل المشغّل ----------
c.st["approvals"]["a9"] = {"id": "a9", "project": pid, "task": "t1", "agent": "engineer", "action": "shell",
                           "details": "echo hi", "status": "pending", "used": False}
P["tasks"] = [{"id": "t1", "title": "x", "description": "", "role": "engineer", "deps": [], "status": "blocked",
               "attempts": 0, "output": "", "feedback": "", "agent": "engineer"}]
c.save()
open(store.path("RUNNER"), "w").write(str(os.getppid()))      # مشغّل ثاني "شغال"
assert store.runner_alive()
store.enqueue("decision", id="a9", ok=True)
assert store.load()["approvals"]["a9"]["status"] == "pending", "must not apply while another runner is alive"
try:
    store.claim_runner(); raise SystemExit("two runners")
except SystemExit as ex:
    assert "مشغّل" in str(ex)
os.remove(store.path("RUNNER"))
c2 = City()                                                    # ما في مشغّل: بيطبّق الطابور
assert c2.st["approvals"]["a9"]["status"] == "approved"
assert c2.st["projects"][pid]["tasks"][0]["status"] == "pending"
store.enqueue("decision", id="nope", ok=True)                  # قرار غلط ما بيكسر شي
City()

# ---------- 5) واجهة الويب ----------
from city import web
os.environ["CITY_WEB_TOKEN"] = "tok-123"
srv = web.make_server("127.0.0.1", 0)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"


def req(path, data=None, opener=None, headers=None):
    r = urllib.request.Request(base + path, data=urllib.parse.urlencode(data).encode() if data else None,
                               headers=headers or {})
    try:
        resp = (opener or urllib.request.build_opener()).open(r)
        return resp.status, resp.read().decode()
    except urllib.error.HTTPError as ex:
        return ex.code, ex.read().decode()


assert req("/")[0] == 401
assert req("/api/state")[0] == 401
assert req("/?t=wrong")[0] == 401
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
code, body = req("/?t=tok-123", opener=op)
assert code == 200 and "Agent City" in body and "tok-123" not in base, code
store.enqueue("request", text="<script>alert(1)</script> بدي تقرير")
City()
code, body = req("/", opener=op)
assert "<script>alert(1)</script>" not in body and "&lt;script&gt;" in body, "XSS"
assert req("/stop", {"x": 1}, opener=op)[0] == 403, "POST without csrf must fail"
assert req("/stop", {"csrf": "tok-123"})[0] == 403, "csrf without cookie must fail"
req("/stop", {"csrf": "tok-123"}, opener=op)
assert store.killed()
req("/resume", {"csrf": "tok-123"}, opener=op)
assert not store.killed()
c.st = store.load()
c.st["approvals"]["a10"] = dict(c.st["approvals"]["a9"], id="a10", status="pending")
c.st["projects"][pid]["tasks"][0]["status"] = "blocked"
c.save()
code, body = req("/", opener=op)
assert "a10" in body and "موافقة" in body
req("/decide", {"csrf": "tok-123", "id": "a10", "ok": "0"}, opener=op)
assert store.load()["approvals"]["a10"]["status"] == "denied"
req("/add", {"csrf": "tok-123", "text": "مشروع من الموبايل"}, opener=op)
assert any(p["request"] == "مشروع من الموبايل" for p in store.load()["projects"].values())
st = json.loads(req("/api/state", headers={"X-City-Token": "tok-123"})[1])
assert any(p.get("integrity") for p in st["projects"]), "integrity warnings exposed to owner"
srv.shutdown()
print("ALL IMPROVEMENT TESTS PASSED")

# ---------- 6) FileBackend: المدينة بدون API (الرد بييجي من ملف) ----------
import threading as _th, time as _time
from city import llm
fb = llm.FileBackend(timeout=20)
def _answer():
    d = os.path.join(fb.dir, "inbox")
    while not os.listdir(d):
        _time.sleep(0.1)
    n = sorted(os.listdir(d))[0].split(".")[0]
    json.dump({"content": [{"type": "text", "text": "ok"}, {"type": "tool_use", "name": "list_files", "input": {}}]},
              open(os.path.join(fb.dir, "outbox", f"{n}.json"), "w"))
_th.Thread(target=_answer, daemon=True).start()
r = fb.chat("You are x", [{"role": "user", "content": "hi"}], [])
assert r.text == "ok" and r.tool_calls[0]["name"] == "list_files" and r.stop_reason == "tool_use" and r.tokens > 0
assert r.tool_calls[0]["id"], "tool_use id generated"
print("FILE BACKEND OK")

# ---------- 7) مهارات الـ seed بتتحدّث (bug ظهر بتشغيل مشروع الذهب الحقيقي: الايجنت قرا مهارة قديمة) ----------
sk = store.path("skills", "gold_toolkit.md")
open(sk, "w").write("description: stale old version\n")
store.init()
assert "protocol.Protocol" in open(sk, encoding="utf-8").read(), "seed skill not refreshed"
try:
    tools.save_skill(ctx, {"name": "gold_toolkit", "description": "x", "content": "y"}); raise SystemExit("seed skill overwritten")
except PermissionError:
    pass
print("SEED SKILL REFRESH OK")

# ---------- 8) صفحة المدينة ----------
from city import cityview
h = cityview.render(fragment=False)
assert "<!doctype html>" in h and "NEXUS" in h and '"key": "engineer"' in h and "مجلس المدينة" in h
assert "<script>alert(1)" not in h and "\\u003cscript\\u003ealert(1)" in h, "user text must not break out of the data JSON"
assert "هيكل الشركة" in cityview.render_classic()
assert "Agent City" in cityview.render() and "esc(" in cityview.render()
print("CITY VIEW OK")

# ---------- 9) أوامر صفحة المدينة (inbox-apply) ----------
import subprocess
def ia(cmd):
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "..", "agentcity.py"), "inbox-apply", json.dumps(cmd)],
                       capture_output=True, text=True, env={**os.environ})
    return json.loads(r.stdout.strip().splitlines()[-1])
r = ia({"kind": "request", "text": "جرّبوا أفكار على الفضة"})
assert r["status"] == "applied" and "مشروع" in r["note"], r
assert ia({"kind": "request", "text": "x"})["status"] == "rejected"
r = ia({"kind": "request", "text": "حسّنوا سرعة فحص المختبر", "target": "engineer"})
assert r["status"] == "applied"
last = max(store.load()["projects"].values(), key=lambda P: P["created"] + P["id"].zfill(5))
assert "'engineer' agent" in last["request"], last["request"]
assert ia({"kind": "request", "text": "فكرة جديدة للذهب", "target": "lab"})["status"] == "applied"
assert ia({"kind": "request", "text": "مهمة لحي وهمي", "target": "../../etc"})["status"] == "rejected"
assert ia({"kind": "approve", "approval": "nope"})["status"] == "rejected"
assert ia({"kind": "hack"})["status"] == "rejected"
assert ia({"kind": "stop"})["status"] == "applied" and store.killed()
assert ia({"kind": "resume"})["status"] == "applied" and not store.killed()
st = store.load()
st["approvals"]["a77"] = {"id": "a77", "project": pid, "task": "t1", "agent": "engineer", "action": "shell", "details": "ls", "status": "pending", "used": False}
store.save(st)
assert ia({"kind": "deny", "approval": "a77"})["status"] == "applied"
assert store.load()["approvals"]["a77"]["status"] == "denied"
h = cityview.render()
assert 'id="b-send"' in h and 'collection("inbox")' in h
print("INBOX APPLY OK")
