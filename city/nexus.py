"""NEXUS: صفحة المدينة بشكل "غرفة قيادة" (خريطة متساوية القياس، أحياء للايجنت، لوحة الحي، بث مباشر، المختبر).
كل الأرقام من state.json + audit.jsonl + lab/ الحقيقيين. صفحة وحدة: HTML + CSS + JS، بدون مكتبات."""
import collections, json, os
from . import store, tools
from .cityview import EVENT_AR, ROLE_AR, STATUS_AR, TOOL_AR, _audit

# حي لكل دور: اسم، نوع، لون، مكان على الشبكة (x, y بخلايا)، عرض/عمق المبنى
DISTRICTS = {
    "ceo":        ("مجلس المدينة", "القيادة", "#8B7CFF", (0, 0), (3, 3)),
    "researcher": ("مختبرات البحث", "بحث", "#3DF5A0", (-5, -4), (2, 2)),
    "engineer":   ("ورشة الكود", "بناء", "#3DE0FF", (5, -4), (2, 3)),
    "analyst":    ("مركز البيانات", "تحليل", "#6FA8FF", (-6, 3), (3, 2)),
    "writer":     ("استوديو المحتوى", "كتابة", "#FFB547", (6, 3), (2, 2)),
    "qa":         ("برج الرقابة", "جودة", "#FF7A90", (0, 7), (2, 2)),
    "lab":        ("مختبر الاستراتيجيات", "بحث تداول", "#3DE0FF", (0, -8), (1, 1)),
}
EXTRA_COLORS = ["#B9B0FF", "#7FF0C8", "#FFD27A", "#9FC4FF"]
AGENT_DESC = {
    "researcher": "بيبحث بالمصادر وبيقارنها، وبيكتب الأفكار والفرضيات قبل أي تجربة.",
    "engineer": "بيكتب الكود وبيختبره قبل ما يقول إنه شغال. كوده بيشتغل معزول جوا Docker.",
    "analyst": "بيحلل البيانات وبيبني الاستراتيجيات وبيقدّمها للمختبر، بمنهجية صارمة بدون تسريب بيانات.",
    "writer": "بيكتب التقارير والسجلات من شغل الفريق، وبالأرقام الحقيقية بس.",
    "qa": "بيراجع كل مهمة بشكل مستقل: بيفتح الملفات، بيشغّل الكود، وبيقارن الأرقام قبل ما تنحسب المهمة خلصت.",
}
ROLE_DESC = {
    "ceo": "بيستلم طلباتك، بيقسمها لمهام، بيوزعها على الأحياء، وبيكتبلك التقرير الأخير. HR جواته بيوظف أدوار جديدة.",
    "lab": "الأفكار بتنقدّم هون، والمدينة بتقيّمها بكود ثابت جوا Docker. المباني المضوية بالاختبار على المستقبل، والمطفية انرفضت.",
}


def payload():
    st, au = store.load(), _audit()
    agents, projects = st["agents"], sorted(st["projects"].values(), key=lambda p: p["created"])
    tool_n = collections.Counter(e.get("agent") for e in au if e.get("event") == "tool")
    kinds = collections.defaultdict(collections.Counter)
    days = collections.defaultdict(collections.Counter)
    for e in au:
        if e.get("event") == "tool":
            kinds[e.get("agent")][e.get("tool")] += 1
            days[e.get("agent")][e.get("t", "")[:13]] += 1
    work = collections.defaultdict(list)
    for P in projects:
        for t in P["tasks"]:
            if t.get("agent"):
                work[t["agent"]].append({"p": P["id"], "title": t["title"][:70], "st": t["status"],
                                         "st_ar": STATUS_AR.get(t["status"], t["status"]), "att": t["attempts"]})
    ceo_n = sum(1 for e in au if e.get("event") in ("planned", "recovered")) + sum(P["status"] == "done" for P in projects)
    try:
        from . import lab as _lab
        board, trials = _lab.board(), _lab.trials()
    except Exception:
        board, trials = {}, []
    ds, extra = [], 0
    def district(key, name, kind, color, pos, size, n, desc, tl, jobs, agent=None):
        hrs = days.get(agent or key, {})
        bars = ([0] * 12 + [hrs[k] for k in sorted(hrs)])[-12:]
        ds.append({"key": key, "name": name, "kind": kind, "color": color, "x": pos[0], "y": pos[1], "w": size[0], "d": size[1],
                   "n": n, "desc": desc, "tools": tl, "jobs": jobs, "bars": bars,
                   "top": [f"{TOOL_AR.get(k, k)} ×{v}" for k, v in kinds.get(agent or key, collections.Counter()).most_common(3)]})
    district("ceo", *DISTRICTS["ceo"][:5], ceo_n, ROLE_DESC["ceo"], [],
             [{"p": P["id"], "title": P["request"][:70].replace("\n", " "), "st": P["status"],
               "st_ar": STATUS_AR.get(P["status"], P["status"]), "att": 1} for P in projects[::-1]])
    for name, a in agents.items():
        if name in DISTRICTS:
            dn, kind, color, pos, size = DISTRICTS[name]
        else:                                           # موظفين HR الجداد بياخدوا أماكن فاضية
            spots = [(-9, -1), (9, -1), (-4, 9), (4, 9)]
            dn, kind, color, pos, size = name, ROLE_AR.get(a["role"], a["role"]), EXTRA_COLORS[extra % 4], spots[extra % 4], (2, 2)
            extra += 1
        district(name, dn, kind, color, pos, size, tool_n.get(name, 0), AGENT_DESC.get(name, a["instructions"]),
                 [{"t": TOOL_AR.get(t, t), "risk": {"shell": "approve", "run_python": "box", "fetch_url": "net"}.get(t, "")} for t in a["tools"]],
                 work.get(name, []), agent=name)
    strategies = [{"name": k, "status": v.get("status"), "agent": v.get("agent", ""), "hyp": (v.get("hypothesis") or "")[:160],
                   "val": (v.get("val") or {}).get("sharpe"), "bh": (v.get("val") or {}).get("bh_sharpe"),
                   "fw": v.get("forward") or {}, "since": v.get("since"), "why": "; ".join(v.get("reasons") or [])[:160]}
                  for k, v in board.items()]
    dn, kind, color, pos, size = DISTRICTS["lab"]
    district("lab", dn, kind, color, pos, size, len(trials), ROLE_DESC["lab"], [],
             [{"p": s["agent"], "title": s["name"], "st": "done" if s["status"] == "forward" else "failed",
               "st_ar": {"forward": "بالاختبار على المستقبل", "rejected": "انرفضت", "waitlist": "بالدور", "error": "خطأ"}.get(s["status"], s["status"]),
               "att": 1} for s in strategies])
    feed = []
    for e in [e for e in au if e.get("event") in EVENT_AR][-60:][::-1]:
        ev, det = e["event"], ""
        if ev == "task":
            det = f'{e.get("project")}/{e.get("task")} · {e.get("agent")} · {STATUS_AR.get(e.get("status"), e.get("status"))}'
        elif ev == "planned":
            det = f'{e.get("project")}: ' + "، ".join(f"{a}→{b}" for a, b in e.get("tasks", []))
        elif ev == "request":
            det = f'{e.get("project")}: {str(e.get("text", ""))[:80]}'
        elif ev == "lab_trial":
            det = f'{e.get("name")} · {e.get("agent")} · {e.get("verdict")}'
        elif ev == "lab_daily":
            det = f'أيام مستقبل: {e.get("forward_days")} · تحت الاختبار: {e.get("active")}'
        elif ev in ("approval_requested", "approval"):
            det = f'{e.get("id", "")} {e.get("action", "")} {e.get("details", "")}'[:100]
        elif ev == "final_test_opened":
            det = e.get("project", "")
        elif ev == "skill_saved":
            det = e.get("name", "")
        elif ev == "tamper_restored":
            det = "، ".join(os.path.basename(f) for f in e.get("files", []))
        feed.append({"t": e.get("t", "")[5:16], "ev": EVENT_AR[ev], "det": det,
                     "bad": ev in ("integrity_violation", "task_error", "refusal")})
    tasks = [t for P in projects for t in P["tasks"]]
    pend = [a for a in st["approvals"].values() if a["status"] == "pending"]
    return {
        "stats": {"agents": len(agents), "projects": len(projects), "done": sum(t["status"] == "done" for t in tasks),
                  "tasks": len(tasks), "tools": sum(tool_n.values()), "tokens": sum(P["tokens"] for P in projects),
                  "forward": sum(s["status"] == "forward" for s in strategies), "trials": len(trials),
                  "attention": len(pend) + sum(P["status"] in ("blocked", "needs_attention", "paused_error") for P in projects)},
        "districts": ds, "strategies": strategies, "feed": feed, "stopped": store.killed(),
        "approvals": [{"id": a["id"], "action": a["action"], "details": str(a["details"])[:300], "agent": a["agent"],
                       "project": a["project"]} for a in pend],
        "lessons": st["lessons"][-6:], "skills": [l[2:] for l in tools.skill_index().splitlines() if l.startswith("- ")],
        "projects": [{"id": P["id"], "status": P["status"], "st_ar": STATUS_AR.get(P["status"], P["status"]),
                      "req": P["request"][:140].replace("\n", " "), "tokens": P["tokens"], "n": len(P["tasks"]),
                      "done": sum(t["status"] == "done" for t in P["tasks"])} for P in projects[::-1]],
    }


HTML = r"""<title>NEXUS · Agent City</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
/* NEXUS command deck (deliberately single dark look): top status bar, district panel on the right, isometric city map, then live feed / lab / projects */
:root{color-scheme:dark;--bg:#070B14;--panel:#0D1422;--panel2:#111B30;--line:rgba(120,160,255,.14);--line2:rgba(120,160,255,.25);
  --ink:#E6ECFA;--mut:#94A1BF;--mut2:#A6B2CE;--cyan:#3DE0FF;--violet:#8B7CFF;--green:#3DF5A0;--amber:#FFB547;--pink:#FF7A90;--blue:#6FA8FF;
  --f:"Cairo",system-ui,sans-serif;--m:"JetBrains Mono",ui-monospace,Menlo,monospace}
*{box-sizing:border-box}
html,body{background:var(--bg);color:var(--ink)}
body{margin:0;font:15px/1.6 var(--f)}
.deck{min-height:100vh;background:radial-gradient(1200px 700px at 40% 0%,#101C3C 0%,var(--bg) 65%)}
.mono{font-family:var(--m);font-variant-numeric:tabular-nums}
header{display:flex;flex-wrap:wrap;align-items:center;gap:12px 22px;padding-block:12px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));border-bottom:1px solid var(--line);background:rgba(7,11,20,.85);position:sticky;top:env(safe-area-inset-top,0px);z-index:20;backdrop-filter:blur(6px)}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);background:var(--bg);z-index:30}
.logo{display:flex;align-items:center;gap:12px}
.logo .mk{width:36px;height:36px;border-radius:10px;border:1.5px solid var(--cyan);box-shadow:0 0 16px #3DE0FF66;display:grid;place-items:center}
.logo b{font-weight:800;font-size:18px;letter-spacing:.14em;direction:ltr;display:block;text-align:right}
.logo small{font-size:12px;color:var(--mut);display:block;margin-top:-4px}
.pills{display:flex;flex-wrap:wrap;gap:8px;flex:1 1 320px}
.pill{display:flex;align-items:center;gap:8px;padding:5px 12px;border-radius:10px;background:var(--panel);border:1px solid var(--line);font-size:14px;white-space:nowrap}
.pill span:first-child{color:var(--mut)}
.pill.warn{border-color:rgba(255,181,71,.4)}.pill.warn .mono{color:var(--amber)}
.dot{width:7px;height:7px;border-radius:50%;background:var(--green);display:inline-block}
.live{animation:pulse 1.8s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:.45}50%{opacity:1}}
.grid{display:flex;flex-wrap:wrap;gap:16px;padding-block:16px 28px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));align-items:flex-start}
aside{flex:1 1 300px;max-width:360px;min-width:0;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px;display:flex;flex-direction:column;gap:16px}
@media (max-width:760px){aside{max-width:none}}
.kind{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:700}
.kind i{width:8px;height:8px;border-radius:50%;display:inline-block}
.dname{font-size:26px;font-weight:800;line-height:1.3}
.ddesc{font-size:14px;color:var(--mut2);line-height:1.7;margin-top:4px}
.tiles{display:flex;gap:8px}
.tile{flex:1;padding:10px 6px;border-radius:12px;background:var(--panel2);border:1px solid rgba(120,160,255,.1);text-align:center;min-width:0}
.tile .mono{font-size:20px;font-weight:500}.tile div:last-child{font-size:12px;color:var(--mut)}
.h{font-size:13px;color:var(--mut);margin-bottom:8px;font-weight:600}
.bars{display:flex;align-items:flex-end;gap:5px;height:44px}
.bars div{flex:1;border-radius:3px;opacity:.85;min-height:3px}
.empty{font-size:13px;color:var(--mut)}
.job{padding:9px 12px;border-radius:10px;background:var(--panel2);border:1px solid rgba(120,160,255,.1);margin-bottom:8px;font-size:14px;display:flex;justify-content:space-between;gap:10px}
.job span:first-child{min-width:0;overflow-wrap:anywhere}
.st{font-size:12px;font-weight:700;white-space:nowrap}
.st.done{color:var(--green)}.st.failed,.st.blocked,.st.needs_attention{color:var(--pink)}.st.running,.st.pending,.st.queued{color:var(--amber)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{display:inline-flex;align-items:center;gap:6px;padding:3px 11px;border-radius:999px;background:var(--panel2);border:1px solid var(--line);font-size:12.5px}
.chip.approve{border-color:rgba(255,122,144,.55);color:#FFB3C0}.chip.box{border-color:rgba(61,224,255,.5);color:#9DEEFF}.chip.net{border-color:rgba(255,181,71,.5);color:#FFD599}
main{flex:999 1 600px;min-width:0;display:flex;flex-direction:column;gap:16px}
.map{position:relative;border-radius:18px;border:1px solid rgba(120,160,255,.16);overflow:hidden;background:radial-gradient(700px 420px at 50% 55%,rgba(61,224,255,.09),transparent 70%),#080D1A}
.map{overflow-x:auto;direction:ltr;-webkit-overflow-scrolling:touch}
.stage{position:relative;min-width:760px}
@media (max-width:760px){main{order:-1}}
.map .cap{position:absolute;right:16px;top:12px;direction:rtl;font-size:12px;color:var(--mut);display:flex;gap:14px;z-index:3}
.map svg{display:block;width:100%;height:auto}
.lbl{position:absolute;transform:translate(-50%,-100%);padding:6px 11px;border-radius:10px;background:rgba(13,20,34,.92);border:1px solid;color:var(--ink);font:600 13px var(--f);cursor:pointer;white-space:nowrap;display:flex;align-items:center;gap:8px;z-index:4;min-height:34px;transition:transform .15s ease,box-shadow .15s ease}
.lbl:hover{transform:translate(-50%,-106%)}
.lbl .mono{font-size:11px;color:var(--mut)}
.lbl[aria-pressed="true"]{box-shadow:0 0 22px currentColor}
.lbl:focus-visible,button:focus-visible{outline:2px solid var(--cyan);outline-offset:2px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:16px;min-width:0}
.card h2{font-size:16px;margin:0 0 10px;font-weight:700;display:flex;align-items:center;gap:8px}
.feed{list-style:none;margin:0;padding:0;max-height:420px;overflow:auto}
.feed li{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;padding:7px 0;border-bottom:1px solid var(--line);font-size:13.5px}
.feed time{font-family:var(--m);font-size:11.5px;color:var(--mut);direction:ltr;grid-row:span 2;padding-top:2px}
.feed .det{color:var(--mut);font-size:12.5px;overflow-wrap:anywhere}
.feed li.bad b{color:var(--pink)}
.strat{padding:10px 12px;border-radius:12px;background:var(--panel2);border:1px solid var(--line);margin-bottom:8px}
.strat.fw{border-color:rgba(61,224,255,.55);box-shadow:0 0 18px rgba(61,224,255,.12)}
.strat .top{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.strat .nm{font-family:var(--m);font-size:13px;direction:ltr}
.strat .hy{font-size:12.5px;color:var(--mut);margin-top:2px}
.meter{display:flex;gap:14px;font-size:12px;color:var(--mut);margin-top:6px;flex-wrap:wrap}
.meter b{font-family:var(--m);color:var(--ink);font-weight:500}
.note{font-size:12.5px;color:var(--mut);margin:0 0 10px}
.proj{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px solid var(--line);font-size:13.5px}
.proj .r{min-width:0;overflow-wrap:anywhere}
ul.plain{margin:0;padding-inline-start:18px;font-size:13px;color:var(--mut2)}
.hbtns{display:flex;gap:8px;flex-wrap:wrap}
.btn{min-height:44px;padding:0 16px;border-radius:10px;font:700 14px var(--f);cursor:pointer;border:1px solid var(--line2);background:var(--panel2);color:var(--ink)}
.btn.pri{background:var(--cyan);border:none;color:#04121A}
.btn.stop{background:transparent;border-color:rgba(255,122,144,.6);color:var(--pink)}
.btn.go{background:transparent;border-color:rgba(61,245,160,.6);color:var(--green)}
.btn.ok{background:var(--green);border:none;color:#03140C}
.btn.no{background:transparent;border-color:rgba(255,122,144,.6);color:var(--pink)}
.btn[disabled]{opacity:.45;cursor:not-allowed}
.cmdbox{display:flex;flex-direction:column;gap:10px;border-top:1px solid var(--line);padding-top:16px}
.cmdbox label{font-size:13px;color:var(--mut)}
textarea{resize:vertical;min-height:84px;padding:12px;border-radius:10px;background:var(--bg);border:1px solid var(--line2);color:var(--ink);font:15px/1.6 var(--f)}
textarea:focus-visible{outline:2px solid var(--cyan);outline-offset:1px}
.msg{font-size:13px;color:var(--mut);min-height:1.2em}
.msg.err{color:var(--pink)}.msg.ok{color:var(--green)}
.appr{padding:12px;border-radius:12px;background:var(--panel2);border:1px solid rgba(255,181,71,.4);margin-bottom:10px}
.appr code{display:block;font-family:var(--m);font-size:12.5px;color:#FFD599;direction:ltr;text-align:left;margin:6px 0 10px;overflow-wrap:anywhere}
.cmd{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px solid var(--line);font-size:13.5px}
.cmd .r{min-width:0;overflow-wrap:anywhere}.cmd .note2{font-size:12.5px;color:var(--mut)}
.badge{font-size:12px;font-weight:700;white-space:nowrap;padding:2px 9px;border-radius:999px;border:1px solid}
.badge.pending{color:var(--amber);border-color:rgba(255,181,71,.5)}.badge.applied{color:var(--green);border-color:rgba(61,245,160,.5)}.badge.rejected{color:var(--pink);border-color:rgba(255,122,144,.5)}
@media (prefers-reduced-motion:reduce){.live,.walker,.packet{animation:none!important}}
</style>
<div class="deck" dir="rtl" lang="ar">
<header>
  <div class="logo"><div class="mk"><svg width="18" height="18" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M2 13V3l6 7V3M14 3v10" stroke="#3DE0FF" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
  <div><b>NEXUS</b><small>مدينة الـ Agents تبعك</small></div></div>
  <div class="pills" id="pills"></div>
  <div class="hbtns"><button type="button" class="btn stop" id="b-stop">⛔ إيقاف طوارئ</button><button type="button" class="btn go" id="b-resume">▶ استئناف</button></div>
</header>
<div class="grid">
  <aside aria-live="polite" id="side"></aside>
  <main>
    <div class="map" id="map"><div class="stage" id="stage"><div class="cap"><span>خريطة المدينة</span><span style="color:var(--green)">● من بيانات حقيقية</span></div></div></div>
    <div class="cols">
      <section class="card"><h2>بانتظار موافقتك</h2><div id="apprs"></div></section>
      <section class="card"><h2>صندوق الأوامر</h2><p class="note">المدينة بتقرأ أوامرك وبتنفّذها بجولتها اليومية (23:17 UTC)، أو فوراً إذا كنت عم تحكي مع Claude. الحالة بتتحدّث هون لحالها.</p><div id="inbox"><div class="empty">عم يحمّل...</div></div></section>
    </div>
    <div class="cols">
      <section class="card"><h2><span class="dot live"></span>البث المباشر</h2><ul class="feed" id="feed"></ul></section>
      <section class="card"><h2>مختبر الاستراتيجيات</h2><p class="note" id="labnote"></p><div id="strats"></div></section>
    </div>
    <div class="cols">
      <section class="card"><h2>المشاريع</h2><div id="projs"></div></section>
      <section class="card"><h2>ذاكرة المدينة</h2><div class="h">دروس الشركة</div><ul class="plain" id="lessons"></ul><div class="h" style="margin-top:12px">المهارات</div><ul class="plain" id="skills"></ul></section>
    </div>
  </main>
</div>
</div>
<script>
const D = __DATA__;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const S = D.stats;
$("#pills").innerHTML = [
  ["Agents", S.agents, "live"], ["مشاريع", S.projects], ["مهام خلصت", S.done + "/" + S.tasks],
  ["استعمال أدوات", S.tools], ["بالاختبار على المستقبل", S.forward], ["محاولات المختبر", S.trials],
  ["توكنز", S.tokens.toLocaleString("en")], ["تحتاج انتباهك", S.attention, S.attention ? "warn" : ""]
].map(([k, v, c]) => `<div class="pill ${c === "warn" ? "warn" : ""}">${c === "live" ? '<i class="dot live"></i>' : ""}<span>${k}</span><span class="mono">${esc(v)}</span></div>`).join("");

// ---------- isometric city ----------
const NS = "http://www.w3.org/2000/svg", T = 34, W = 1100, H = 700, OX = W / 2, OY = 330;
const iso = (x, y, z = 0) => [OX + (x - y) * T * 0.866, OY + (x + y) * T * 0.5 - z];
const el = (n, a, p) => { const e = document.createElementNS(NS, n); for (const k in a) e.setAttribute(k, a[k]); p && p.appendChild(e); return e; };
const pts = a => a.map(p => p.join(",")).join(" ");
const shade = (hex, f) => { const n = parseInt(hex.slice(1), 16); const r = Math.round(((n >> 16) & 255) * f), g = Math.round(((n >> 8) & 255) * f), b = Math.round((n & 255) * f); return `rgb(${r},${g},${b})`; };
const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "خريطة المدينة: حي لكل ايجنت، وطول المبنى حسب شغله" }, $("#stage"));
const defs = el("defs", {}, svg);
const glow = el("filter", { id: "glow", x: "-50%", y: "-50%", width: "200%", height: "200%" }, defs);
el("feGaussianBlur", { stdDeviation: "3", result: "b" }, glow); const mg = el("feMerge", {}, glow); el("feMergeNode", { in: "b" }, mg); el("feMergeNode", { in: "SourceGraphic" }, mg);
for (let i = 0; i < 70; i++) el("circle", { cx: (i * 397) % W, cy: (i * 151) % 190, r: i % 3 ? .8 : 1.3, fill: "#BFD4FF", opacity: .25 + (i % 5) / 10 }, svg);
const G = 11;   // ground: -G..G
el("polygon", { points: pts([iso(-G, -G), iso(G, -G), iso(G, G), iso(-G, G)]), fill: "#0A1124", stroke: "rgba(61,224,255,.35)", "stroke-width": 1.5, filter: "url(#glow)" }, svg);
const gridG = el("g", { stroke: "rgba(61,224,255,.06)", "stroke-width": 1 }, svg);
for (let k = -G; k <= G; k += 1) { el("line", { x1: iso(k, -G)[0], y1: iso(k, -G)[1], x2: iso(k, G)[0], y2: iso(k, G)[1] }, gridG); el("line", { x1: iso(-G, k)[0], y1: iso(-G, k)[1], x2: iso(G, k)[0], y2: iso(G, k)[1] }, gridG); }
// streets from council hall to each district
const roads = el("g", { stroke: "#2B3C66", "stroke-width": 2, "stroke-dasharray": "10 10", fill: "none" }, svg);
const hall = D.districts.find(d => d.key === "ceo");
const cen = d => [d.x + d.w / 2, d.y + d.d / 2];
D.districts.filter(d => d.key !== "ceo").forEach(d => { const [a, b] = iso(...cen(hall)), [c, e] = iso(...cen(d)); el("path", { d: `M${a},${b} L${c},${e}`, id: "rd-" + d.key }, roads); });
const maxN = Math.max(1, ...D.districts.filter(d => d.key !== "lab").map(d => d.n));
function box(g, x, y, w, d, h, color, lit, total) {
  const A = iso(x, y), B = iso(x + w, y), C = iso(x + w, y + d), Dd = iso(x, y + d);
  const up = p => [p[0], p[1] - h];
  el("polygon", { points: pts([Dd, C, up(C), up(Dd)]), fill: shade(color, .28) }, g);           // left face (south)
  el("polygon", { points: pts([C, B, up(B), up(C)]), fill: shade(color, .18) }, g);             // right face (east)
  el("polygon", { points: pts([up(A), up(B), up(C), up(Dd)]), fill: shade(color, .5), stroke: color, "stroke-width": 1.2, "stroke-opacity": .8 }, g);
  // windows on the left face, lit = real work
  const cols = Math.max(1, Math.round(w * 2)), rows = Math.max(1, Math.floor(h / 13)); let k = 0;
  for (let r = rows - 1; r >= 0; r--) for (let c = 0; c < cols; c++) {
    const fx = (c + .3) / cols, fx2 = (c + .7) / cols, z1 = 6 + r * 13, z2 = z1 + 6;
    const P = (f, z) => { const p = [Dd[0] + (C[0] - Dd[0]) * f, Dd[1] + (C[1] - Dd[1]) * f - z]; return p; };
    const on = (rows - 1 - r) * cols + c < lit;
    el("polygon", { points: pts([P(fx, z1), P(fx2, z1), P(fx2, z2), P(fx, z2)]), fill: on ? "#FFD27A" : "rgba(120,160,255,.10)", opacity: on ? .95 : 1 }, g);
  }
}
const city = el("g", {}, svg), labels = [];
[...D.districts].sort((a, b) => (a.x + a.y) - (b.x + b.y)).forEach(d => {
  const g = el("g", { "data-k": d.key }, city);
  el("polygon", { points: pts([iso(d.x - .4, d.y - .4), iso(d.x + d.w + .4, d.y - .4), iso(d.x + d.w + .4, d.y + d.d + .4), iso(d.x - .4, d.y + d.d + .4)]), fill: d.color, opacity: .08, stroke: d.color, "stroke-opacity": .35 }, g);
  if (d.key === "lab") {                                // كل استراتيجية مبنى صغير
    const ss = D.strategies.length ? D.strategies : [{ status: "none" }];
    ss.forEach((s, i) => { const x = d.x - 2 + (i % 5) * 1.1, y = d.y - 1 + Math.floor(i / 5) * 1.1; box(g, x, y, .8, .8, s.status === "forward" ? 46 : 22, s.status === "forward" ? "#3DE0FF" : "#4A5878", s.status === "forward" ? 99 : 0, 0); });
    labels.push({ d, at: iso(d.x + .5, d.y - 1, 60) });
  } else {
    const h = 30 + 150 * Math.sqrt(d.n / maxN);
    box(g, d.x, d.y, d.w, d.d, h, d.color, d.key === "ceo" ? Math.min(d.n * 2, 999) : d.n, 0);
    if (d.key === "ceo") el("polygon", { points: pts([iso(d.x + 1.5, d.y + 1.5, h + 70), iso(d.x + 1.2, d.y + 1.5, h), iso(d.x + 1.8, d.y + 1.5, h)]), fill: "url(#beam)", opacity: .7 }, g);
    labels.push({ d, at: iso(d.x + d.w / 2, d.y + d.d / 2, h + 16) });
  }
});
const beam = el("linearGradient", { id: "beam", x1: 0, y1: 0, x2: 0, y2: 1 }, defs); el("stop", { offset: 0, "stop-color": "#8B7CFF", "stop-opacity": 0 }, beam); el("stop", { offset: 1, "stop-color": "#8B7CFF", "stop-opacity": .9 }, beam);
// agents walking along their street (one per real agent)
const motion = !matchMedia("(prefers-reduced-motion: reduce)").matches;
D.districts.filter(d => !["ceo", "lab"].includes(d.key)).forEach((d, i) => {
  const g = el("g", { class: "walker" }, svg);
  el("ellipse", { cx: 0, cy: 0, rx: 5, ry: 2.5, fill: "rgba(0,0,0,.5)" }, g);
  el("rect", { x: -4, y: -15, width: 8, height: 10, rx: 3, fill: d.color }, g);
  el("circle", { cx: 0, cy: -19, r: 3.4, fill: "#F2C9A0" }, g);
  if (motion) { const a = el("animateMotion", { dur: (9 + i * 2) + "s", repeatCount: "indefinite", keyPoints: "0;1;0", keyTimes: "0;.5;1", calcMode: "linear" }, g); el("mpath", { href: "#rd-" + d.key }, a); }
  else { const [x, y] = iso(...cen(d)); g.setAttribute("transform", `translate(${x},${y})`); }
});
// district labels (buttons over the map)
const map = $("#stage");
labels.forEach(({ d, at }) => {
  const b = document.createElement("button");
  b.type = "button"; b.className = "lbl"; b.style.color = d.color; b.style.borderColor = d.color;
  b.style.left = (at[0] / W * 100) + "%"; b.style.top = (at[1] / H * 100) + "%";
  b.innerHTML = `<span style="color:var(--ink)">${esc(d.name)}</span><span class="mono">${d.n}</span>`;
  b.setAttribute("aria-label", `${d.name}: ${d.n}`); b.dataset.k = d.key;
  b.addEventListener("click", () => pick(d.key)); map.appendChild(b);
});

// ---------- district panel ----------
function pick(k) {
  const d = D.districts.find(x => x.key === k);
  document.querySelectorAll(".lbl").forEach(b => b.setAttribute("aria-pressed", b.dataset.k === k));
  const unit = k === "ceo" ? "قرارات" : k === "lab" ? "محاولات" : "استعمال أدوات";
  const done = d.jobs.filter(j => j.st === "done").length;
  const bars = d.bars.some(b => b) ? (() => { const m = Math.max(...d.bars); return `<div class="bars" aria-hidden="true">${d.bars.map(b => `<div style="height:${Math.max(3, b / m * 44)}px;background:${d.color}"></div>`).join("")}</div>`; })() : '<div class="empty">لسا ما في نشاط مسجّل.</div>';
  const jobs = d.jobs.length ? d.jobs.slice(0, 6).map(j => `<div class="job"><span>${esc(j.p)} · ${esc(j.title)}</span><span class="st ${esc(j.st)}">${esc(j.st_ar)}</span></div>`).join("") : '<div class="empty">ما اشتغل بأي مشروع لسا.</div>';
  const tools = d.tools.length ? `<div><div class="h">الصلاحيات</div><div class="chips">${d.tools.map(t => `<span class="chip ${t.risk}">${esc(t.t)}</span>`).join("")}</div></div>` : "";
  $("#side").innerHTML = `
    <div><div class="kind" style="color:${d.color}"><i style="background:${d.color};box-shadow:0 0 10px ${d.color}"></i>${esc(d.kind)}</div>
    <div class="dname">${esc(d.name)}</div><div class="ddesc">${esc(d.desc)}</div></div>
    <div class="tiles"><div class="tile"><div class="mono">${d.n}</div><div>${unit}</div></div>
    <div class="tile"><div class="mono">${d.jobs.length}</div><div>${k === "ceo" ? "مشاريع" : k === "lab" ? "أفكار" : "مهام"}</div></div>
    <div class="tile"><div class="mono" style="color:var(--green)">${done}</div><div>${k === "lab" ? "بالمستقبل" : "خلصت"}</div></div></div>
    <div><div class="h">النشاط حسب الساعة</div>${bars}</div>
    ${d.top.length ? `<div><div class="h">أكتر شي بيستعمل</div><div class="chips">${d.top.map(t => `<span class="chip">${esc(t)}</span>`).join("")}</div></div>` : ""}
    <div><div class="h">${k === "ceo" ? "المشاريع" : k === "lab" ? "الأفكار" : "الشغل"}</div>${jobs}</div>${tools}
    <div class="cmdbox"><div class="h" style="margin:0">أمر جديد للمدينة</div>
      <label for="cmdtext">الأمر بيوصل للمدير، وهو بيخطط وبيوزع على الأحياء</label>
      <textarea id="cmdtext" maxlength="4000" placeholder="مثال: جرّبوا أفكار على الفضة كمان، وقارنوها مع الذهب"></textarea>
      <button type="button" class="btn pri" id="b-send">أرسل للمدينة</button><div class="msg" id="sendmsg" role="status"></div></div>
    <div style="font-size:12px;color:var(--mut);border-top:1px solid var(--line);padding-top:12px">الألوان: <span class="chip approve">بحتاج موافقتك</span> <span class="chip box">معزول بـ Docker</span> <span class="chip net">إنترنت</span></div>`;
}
pick("ceo");
{ const m = $("#map"); m.scrollLeft = (m.scrollWidth - m.clientWidth) / 2; }

// ---------- feed / lab / projects / memory ----------
$("#feed").innerHTML = D.feed.map(f => `<li class="${f.bad ? "bad" : ""}"><time>${esc(f.t)}</time><b>${esc(f.ev)}</b><span class="det">${esc(f.det)}</span></li>`).join("") || '<li class="empty">ولا شي لسا</li>';
$("#labnote").textContent = `${S.trials} محاولة لحد هلأ. كل ما زادت المحاولات زاد احتمال نجاح بالصدفة، فالحكم الحقيقي هو الأيام الجديدة.`;
const pc = x => (x >= 0 ? "+" : "−") + Math.abs(x * 100).toFixed(2) + "%";
$("#strats").innerHTML = [...D.strategies].sort((a, b) => (b.status === "forward") - (a.status === "forward")).map(s => {
  const fw = s.status === "forward";
  const lbl = { forward: "بالاختبار على المستقبل", rejected: "انرفضت", waitlist: "بالدور", error: "خطأ بالكود" }[s.status] || s.status;
  const meter = fw ? `<div class="meter"><span>من <b>${esc(s.since)}</b></span><span>أيام <b>${s.fw.days || 0}</b></span><span>المؤشر <b>${pc(s.fw.return || 0)}</b></span><span>شراء واحتفاظ <b>${pc(s.fw.buy_hold || 0)}</b></span><span>هلأ <b>${s.fw.position_now ? "شاري" : "برّا"}</b></span></div>`
                   : `<div class="meter"><span>Sharpe تحقق <b>${s.val ?? "—"}</b> مقابل <b>${s.bh ?? "—"}</b></span></div><div class="hy">${esc(s.why)}</div>`;
  return `<div class="strat ${fw ? "fw" : ""}"><div class="top"><span class="nm">${esc(s.name)}</span><span class="st ${fw ? "done" : "failed"}">${lbl}</span></div><div class="hy">${esc(s.hyp)}</div>${meter}</div>`;
}).join("") || '<div class="empty">ما في أفكار لسا.</div>';
$("#projs").innerHTML = D.projects.map(p => `<div class="proj"><div class="r"><b class="mono">${esc(p.id)}</b> · ${esc(p.req)}<div class="empty">${p.done}/${p.n} مهام · ${p.tokens.toLocaleString("en")} توكن</div></div><span class="st ${esc(p.status)}">${esc(p.st_ar)}</span></div>`).join("");
// ---------- الأوامر: بتنحفظ بقاعدة بيانات الصفحة (inbox) والمدينة بتنفّذها ----------
const KIND = { request: "طلب جديد", approve: "موافقة", deny: "رفض", stop: "إيقاف طوارئ", resume: "استئناف" };
const STAT = { pending: "بالانتظار", applied: "انتنفّذ", rejected: "انرفض" };
let DB = null, UID = null, lastDraft = "";
function setMsg(t, cls) { const m = $("#sendmsg"); if (m) { m.textContent = t; m.className = "msg " + (cls || ""); } }
function canSend(on, why) {
  document.querySelectorAll("#b-send,#b-stop,#b-resume,.appr .btn").forEach(b => { b.disabled = !on; });
  if (!on && why) { const i = $("#inbox"); if (i) i.innerHTML = `<div class="empty">${esc(why)}</div>`; }
}
async function send(kind, extra = {}) {
  if (!DB) return false;
  try {
    await DB.collection("inbox").add({ kind, ...extra, status: "pending", at: new Date().toISOString(), by: UID || "" });
    return true;
  } catch (e) {
    const t = e && e.code === "not_granted" ? "ما عندك صلاحية ترسل أوامر لهالمدينة." : "ما انحفظ الأمر. جرّب كمان شوي.";
    setMsg(t, "err"); return false;
  }
}
function renderApprovals() {
  const box = $("#apprs");
  if (!D.approvals.length) { box.innerHTML = '<div class="empty">ما في شي بانتظارك. أي أمر shell أو فعل خارجي بيطلع هون.</div>'; return; }
  box.innerHTML = D.approvals.map(a => `<div class="appr" data-id="${esc(a.id)}"><div><b>${esc(a.action)}</b> <span class="empty">${esc(a.id)} · ${esc(a.agent)} @ ${esc(a.project)}</span></div><code>${esc(a.details)}</code>
    <div class="hbtns"><button type="button" class="btn ok" data-act="approve">وافق</button><button type="button" class="btn no" data-act="deny">ارفض</button></div><div class="msg"></div></div>`).join("");
  box.querySelectorAll(".appr .btn").forEach(b => b.addEventListener("click", async () => {
    const card = b.closest(".appr"), id = card.dataset.id, act = b.dataset.act;
    card.querySelectorAll(".btn").forEach(x => x.disabled = true);
    const ok = await send(act, { approval: id });
    card.querySelector(".msg").textContent = ok ? (act === "approve" ? "قرار الموافقة بالطابور." : "قرار الرفض بالطابور.") : "ما انحفظ القرار.";
    if (!ok) card.querySelectorAll(".btn").forEach(x => x.disabled = false);
  }));
}
renderApprovals();
document.addEventListener("click", async ev => {
  const t = ev.target.closest("button"); if (!t) return;
  if (t.id === "b-send") {
    const ta = $("#cmdtext"), text = ta.value.trim();
    if (text.length < 5) { setMsg("اكتب الأمر أول (5 حروف على الأقل).", "err"); return; }
    t.disabled = true; setMsg("عم يرسل...");
    if (await send("request", { text })) { ta.value = ""; lastDraft = ""; setMsg("وصل للصندوق. المدينة رح تستلمه بجولتها الجاية.", "ok"); }
    t.disabled = false;
  } else if (t.id === "b-stop" || t.id === "b-resume") {
    const kind = t.id === "b-stop" ? "stop" : "resume";
    t.disabled = true;
    const ok = await send(kind);
    t.textContent = ok ? (kind === "stop" ? "⛔ الإيقاف بالطابور" : "▶ الاستئناف بالطابور") : t.textContent;
    if (!ok) t.disabled = false;
  }
});
// keep a typed draft when the side panel re-renders on district change
document.addEventListener("input", ev => { if (ev.target.id === "cmdtext") lastDraft = ev.target.value; });
const _pick = pick; pick = k => { _pick(k); const ta = $("#cmdtext"); if (ta) ta.value = lastDraft; canSend(!!DB); };
canSend(false);
(async () => {
  if (!(window.claude && claude.use)) { canSend(false, "الأزرار بتشتغل لما تفتح هالصفحة على claude.ai."); return; }
  const [db, user] = await Promise.all([claude.use("db"), claude.use("user")]);
  if (!db) { canSend(false, "الأوامر مش متاحة هون (لازم تكون مسجّل دخول وإلك صلاحية على الصفحة)."); return; }
  DB = db; UID = user ? await user.id() : null;
  const timer = setTimeout(() => { const i = $("#inbox"); if (i && i.textContent.includes("عم يحمّل")) i.innerHTML = '<div class="empty">ما قدرت أقرأ الصندوق هلأ.</div>'; }, 10000);
  db.collection("inbox").orderBy("at", "desc").limit(25).onSnapshot(snap => {
    clearTimeout(timer); canSend(true);
    const rows = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    $("#inbox").innerHTML = rows.length ? rows.map(c => `<div class="cmd"><div class="r"><b>${esc(KIND[c.kind] || c.kind)}</b>${c.text ? " · " + esc(c.text) : ""}${c.approval ? " · " + esc(c.approval) : ""}
      <div class="note2">${esc((c.at || "").slice(0, 16).replace("T", " "))}${c.note ? " · " + esc(c.note) : ""}</div></div><span class="badge ${esc(c.status)}">${esc(STAT[c.status] || c.status)}</span></div>`).join("")
      : '<div class="empty">ما في أوامر لسا. اكتب أمر بلوحة الحي أو اكبس زر.</div>';
  }, e => { clearTimeout(timer); canSend(false, e && e.code === "not_granted" ? "ما عندك صلاحية تشوف صندوق الأوامر." : "ما قدرت أقرأ الصندوق هلأ."); });
})();
$("#lessons").innerHTML = D.lessons.map(l => `<li>${esc(l)}</li>`).join("") || "<li>لسا</li>";
$("#skills").innerHTML = D.skills.map(l => `<li>${esc(l.slice(0, 120))}</li>`).join("");
</script>
"""


def render(fragment=True):
    # كل "<" بيصير \u003c: ولا نص من المستخدم بيقدر يسكّر الـ <script> أو يفتح تعليق HTML
    data = json.dumps(payload(), ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    page = HTML.replace("__DATA__", data)
    if fragment:
        return page
    head, body = page.split("</style>", 1)
    return ('<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'{head}</style></head><body>{body}</body></html>')
