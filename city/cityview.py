"""صفحة "شوف مدينتك": أفق المدينة (بناية لكل ايجنت)، هيكل الشركة، بطاقات الايجنت، المشاريع، والخط الزمني.
كلها من state.json + audit.jsonl الحقيقيين. HTML+CSS بدون JavaScript.

python agentcity.py view --out city.html     # ملف لحاله
python agentcity.py web  ->  /city            # من واجهة الويب
"""
import collections, html, json, os
from . import store, tools

E = html.escape
ROLE_AR = {"researcher": "باحث", "engineer": "مهندس", "analyst": "محلل بيانات", "writer": "كاتب تقارير",
           "qa": "مراقب جودة (QA)"}
TOOL_AR = {"read_file": "قراءة ملفات", "write_file": "كتابة ملفات", "list_files": "تصفح الملفات",
           "run_python": "تشغيل كود (Docker)", "shell": "أوامر shell (بموافقتك)", "fetch_url": "إنترنت (قراءة)",
           "request_approval": "طلب موافقة", "save_skill": "حفظ مهارة", "list_skills": "عرض المهارات",
           "load_skill": "قراءة مهارة"}
RISKY = {"shell": "danger", "run_python": "box", "fetch_url": "net"}
STATUS_AR = {"done": "خلصت", "running": "شغالة", "pending": "بالانتظار", "blocked": "بانتظار موافقتك",
             "failed": "فشلت", "queued": "بالدور", "needs_attention": "بدها انتباه", "paused_budget": "وقفت (السقف)",
             "paused_stop": "وقفت (طوارئ)", "paused_error": "وقفت (خطأ)"}
EVENT_AR = {"request": "طلب جديد من المالك", "planned": "المدير خطط المشروع", "hired": "HR وظّف ايجنت جديد",
            "task": "مهمة انتهت", "approval_requested": "ايجنت طلب موافقتك", "approval": "قرار موافقة",
            "final_test_opened": "انفتح الاختبار النهائي (مرة وحدة)", "integrity_violation": "⚠️ مخالفة نزاهة",
            "skill_saved": "المدينة تعلمت مهارة", "tamper_restored": "رجّعنا ملفات محمية لنسختها الأصلية",
            "recovered": "المدير أعاد صياغة مهمة", "lab_trial": "فكرة انقدّمت للمختبر", "lab_daily": "تحديث اختبار المستقبل", "refusal": "النموذج رفض طلب", "task_error": "خطأ بمهمة",
            "stop": "إيقاف طوارئ", "resume": "استئناف"}


def _audit():
    p = store.path("audit.jsonl")
    if not os.path.exists(p):
        return []
    out = []
    for l in open(p, encoding="utf-8"):
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


def data():
    st, au = store.load(), _audit()
    tool_n = collections.Counter(e.get("agent") for e in au if e.get("event") == "tool")
    tool_kinds = collections.defaultdict(collections.Counter)
    for e in au:
        if e.get("event") == "tool":
            tool_kinds[e.get("agent")][e.get("tool")] += 1
    work = collections.defaultdict(list)            # المهام اللي اشتغلها كل ايجنت
    for P in st["projects"].values():
        for t in P["tasks"]:
            if t.get("agent"):
                work[t["agent"]].append((P["id"], t))
    reviews = collections.Counter()
    for e in au:
        if e.get("event") == "tool" and e.get("agent") == "qa":
            reviews[(e.get("project"), e.get("task"))] += 1
    llm_n = len(os.listdir(store.path("llm", "done"))) // 2 if os.path.isdir(store.path("llm", "done")) else None
    return {"st": st, "audit": au, "tool_n": tool_n, "tool_kinds": tool_kinds, "work": work,
            "qa_reviews": len(reviews), "llm_n": llm_n,
            "skills": [l[2:] for l in tools.skill_index().splitlines() if l.startswith("- ")]}


CSS = """
/* Layout: dusk skyline band (one building per agent, lit windows = real tool calls), then org chart, agent cards, projects, timeline */
:root{
  --bg:#eef1f5; --panel:#ffffff; --ink:#18212d; --mut:#5d6878; --line:#d9dee6;
  --sky1:#c9d6e8; --sky2:#eef1f5; --bldg:#33465f; --bldg2:#46607f; --win:#f2b544; --win-off:#5a6f8c;
  --ok:#21875a; --warn:#b5730f; --bad:#c23b3b; --acc:#2f5f99; --chip:#eef2f8;
  --f-display:"Readex Pro","IBM Plex Sans Arabic",system-ui,sans-serif;
  --f-body:"IBM Plex Sans Arabic","Segoe UI",Tahoma,system-ui,sans-serif;
  --f-mono:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0f1621; --panel:#161f2c; --ink:#e6ebf2; --mut:#93a0b3; --line:#263244;
  --sky1:#0b111a; --sky2:#1a2638; --bldg:#22324a; --bldg2:#2c4060; --win:#ffc35a; --win-off:#34465f;
  --ok:#4cc08a; --warn:#f0a840; --bad:#ff7070; --acc:#8fb4ff; --chip:#1d2838; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0f1621; --panel:#161f2c; --ink:#e6ebf2; --mut:#93a0b3; --line:#263244;
  --sky1:#0b111a; --sky2:#1a2638; --bldg:#22324a; --bldg2:#2c4060; --win:#ffc35a; --win-off:#34465f;
  --ok:#4cc08a; --warn:#f0a840; --bad:#ff7070; --acc:#8fb4ff; --chip:#1d2838; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:15px/1.65 var(--f-body);margin:0}
.wrap{max-width:1040px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:0 48px}
h1,h2,h3{font-family:var(--f-display);text-wrap:balance;margin:0}
h1{font-size:clamp(26px,5vw,38px);font-weight:600;letter-spacing:-.01em}
h2{font-size:20px;font-weight:600;margin-block:40px 14px}
h3{font-size:16px;font-weight:600}
.mut{color:var(--mut)}.num{font-family:var(--f-mono);font-variant-numeric:tabular-nums}
.sky{background:linear-gradient(180deg,var(--sky1),var(--sky2));border-bottom:1px solid var(--line)}
.sky .wrap{padding-block:28px 0}
.lede{max-width:62ch;margin-block:6px 0;color:var(--mut)}
.stats{display:flex;flex-wrap:wrap;gap:8px 22px;margin-block:14px 22px;font-size:13px;color:var(--mut)}
.stats b{color:var(--ink);font-family:var(--f-mono);font-size:15px;font-weight:600}
.skyline{display:flex;align-items:flex-end;gap:clamp(6px,2vw,18px);overflow-x:auto;padding-top:8px}
.b{flex:1 1 0;min-width:74px;display:flex;flex-direction:column;align-items:center}
.tower{width:100%;background:var(--bldg);border-radius:3px 3px 0 0;padding:10px 8px 8px;display:grid;
  grid-template-columns:repeat(4,1fr);gap:5px;align-content:start;position:relative}
.tower.ceo{background:var(--bldg2)}
.tower::before{content:"";position:absolute;top:-10px;left:50%;width:2px;height:10px;background:var(--bldg);transform:translateX(-50%)}
.w{aspect-ratio:1/1.3;border-radius:1px;background:var(--win-off)}
.w.on{background:var(--win);box-shadow:0 0 6px color-mix(in srgb,var(--win) 60%,transparent)}
.b .lbl{font-size:12px;font-weight:600;margin-top:6px;text-align:center}
.b .sub{font-size:11px;color:var(--mut);font-family:var(--f-mono)}
.street{height:10px;background:var(--bldg);opacity:.85}
.legend{font-size:12px;color:var(--mut);margin-block:8px 0;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.legend i{display:inline-block;width:9px;height:12px;border-radius:1px;vertical-align:-2px;margin-inline-end:4px}
.org{display:grid;gap:10px;justify-items:center}
.node{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 16px;text-align:center;min-width:160px}
.node small{display:block;color:var(--mut);font-size:12px}
.node.owner{border-color:var(--acc);border-width:2px}
.vline{width:2px;height:16px;background:var(--line)}
.team{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;border-top:2px solid var(--line);padding-top:14px;max-width:100%}
.side{display:flex;gap:10px;flex-wrap:wrap;justify-content:center}
.node.watch{border-style:dashed}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:8px;min-width:0}
.card .head{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.card .badge{font-size:12px;color:var(--mut);font-family:var(--f-mono)}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip{font-size:12px;background:var(--chip);border:1px solid var(--line);border-radius:99px;padding:1px 9px}
.chip.danger{border-color:var(--bad);color:var(--bad)}
.chip.box{border-color:var(--acc);color:var(--acc)}
.chip.net{border-color:var(--warn);color:var(--warn)}
.card ul{margin:0;padding-inline-start:18px;font-size:13px}
.st{font-size:12px;font-weight:600}
.st.done{color:var(--ok)}.st.failed,.st.blocked{color:var(--bad)}.st.running,.st.pending,.st.queued{color:var(--warn)}
.proj{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;margin-block:0 12px}
.proj .req{margin-block:6px 10px;max-width:70ch}
.flow{display:flex;flex-wrap:wrap;gap:8px;align-items:stretch}
.step{flex:1 1 180px;min-width:0;border:1px solid var(--line);border-radius:8px;padding:8px 10px;border-inline-start:4px solid var(--line)}
.step.done{border-inline-start-color:var(--ok)}.step.failed,.step.blocked{border-inline-start-color:var(--bad)}.step.pending,.step.running{border-inline-start-color:var(--warn)}
.step .who{font-size:12px;color:var(--mut)}
.summary{margin-block:10px 0;padding:10px 12px;background:var(--chip);border-radius:8px;font-size:14px;white-space:pre-wrap}
.warn{color:var(--bad);font-size:13px}
td,th{padding:6px 8px;border-top:1px solid var(--line);vertical-align:top}
.tl{list-style:none;margin:0;padding:0;border-inline-start:2px solid var(--line)}
.tl li{position:relative;padding:4px 14px 8px;font-size:13px}
.tl li::before{content:"";position:absolute;inset-inline-start:-6px;top:10px;width:10px;height:10px;border-radius:50%;background:var(--panel);border:2px solid var(--acc)}
.tl li.bad::before{border-color:var(--bad)}
.tl time{font-family:var(--f-mono);color:var(--mut);font-size:12px;margin-inline-end:6px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
.box{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;min-width:0}
.box ul{margin:0;padding-inline-start:18px;font-size:13px}
footer{margin-top:36px;font-size:12px;color:var(--mut)}
:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
"""


def _windows(n_on, total):
    """الشبابيك المضوية من تحت لفوق (أول شبابيك بالـ HTML = أعلى طابق)."""
    return "".join(f'<i class="w{" on" if k >= total - n_on else ""}"></i>' for k in range(total))


def render(fragment=True):
    d = data()
    st, agents = d["st"], d["st"]["agents"]
    projects = sorted(st["projects"].values(), key=lambda p: p["created"])
    tasks = [t for P in projects for t in P["tasks"]]
    total_tools = sum(d["tool_n"].values())
    tokens = sum(P["tokens"] for P in projects)
    # ---------- الأفق: المدير + بناية لكل ايجنت ----------
    ceo_calls = sum(1 for e in d["audit"] if e.get("event") in ("planned", "recovered")) + \
        sum(1 for P in projects if P["status"] == "done")
    rows = [("ceo", "المدير (CEO)", "يخطط ويوزع", ceo_calls)] + \
           [(n, n, ROLE_AR.get(a["role"], a["role"]), d["tool_n"].get(n, 0)) for n, a in agents.items()]
    mx = max([r[3] for r in rows] + [1])
    sky = []
    for key, name, sub, n in rows:
        per = max(1, -(-mx // 40))                                # شباك لكل `per` استعمال، أقصى ~40 شباك
        on = -(-n // per)
        cap = max(8, 4 * (-(-on // 4)) + 4)                       # طابق فاضي فوق = مكان للشغل الجاي
        sky.append(f'<div class="b"><div class="tower{" ceo" if key == "ceo" else ""}">{_windows(on, cap)}</div>'
                   f'<div class="lbl">{E(name)}</div><div class="sub">{E(sub)} · {n}</div></div>')
    # ---------- هيكل الشركة ----------
    team = [n for n, a in agents.items() if n != "qa"]
    hired = {n for n, a in agents.items() if a.get("hired")}
    org = (f'<div class="org"><div class="node owner"><b>انت (المالك)</b><small>بتحكي مع المدير بس · بتوافق على الأفعال الخطرة</small></div>'
           f'<div class="vline"></div><div class="node"><b>المدير (CEO)</b><small>بيخطط · بيوزع · بيكتبلك التقرير</small></div>'
           f'<div class="vline"></div><div class="team">'
           + "".join(f'<div class="node"><b>{E(n)}</b><small>{E(ROLE_AR.get(agents[n]["role"], agents[n]["role"]))}'
                     f'{" · موظف جديد (HR)" if n in hired else ""}</small></div>' for n in team)
           + '</div><div class="side"><div class="node watch"><b>qa</b><small>بيراجع كل مهمة قبل ما تنحسب</small></div>'
             '<div class="node watch"><b>HR</b><small>بيوظف ايجنت لأدوار جديدة</small></div>'
             '<div class="node watch"><b>فحص المخاطر</b><small>قواعد بالكود (risk.py)، مش رأي</small></div></div></div>')
    # ---------- بطاقات الايجنت ----------
    cards = []
    for n, a in agents.items():
        chips = "".join(f'<span class="chip {RISKY.get(t, "")}">{E(TOOL_AR.get(t, t))}</span>' for t in a["tools"])
        jobs = d["work"].get(n, [])
        kinds = d["tool_kinds"].get(n, collections.Counter())
        top = "، ".join(f"{TOOL_AR.get(k, k)} ×{v}" for k, v in kinds.most_common(3))
        jl = "".join(f'<li>{E(pid)} · {E(t["title"][:60])} <span class="st {E(t["status"])}">{E(STATUS_AR.get(t["status"], t["status"]))}</span></li>'
                     for pid, t in jobs)
        if n == "qa" and d["qa_reviews"]:
            jl = f"<li>راجع {d['qa_reviews']} مهمة بشكل مستقل</li>"
        cards.append(f'<div class="card"><div class="head"><h3>{E(n)}</h3><span class="badge">{d["tool_n"].get(n, 0)} استعمال أداة</span></div>'
                     f'<div class="mut" style="font-size:13px">{E(ROLE_AR.get(a["role"], a["role"]))} · {E(a["instructions"])}</div>'
                     f'<div class="chips">{chips}</div>'
                     + (f'<div style="font-size:13px"><b>أكثر شي استعمل:</b> {E(top)}</div>' if top else "")
                     + (f'<ul>{jl}</ul>' if jl else '<div class="mut" style="font-size:13px">لسا ما اشتغل بأي مشروع.</div>')
                     + "</div>")
    # ---------- المشاريع ----------
    projs = []
    for P in reversed(projects):
        steps = "".join(f'<div class="step {E(t["status"])}"><div><b>{E(t["id"])}</b> {E(t["title"][:70])}</div>'
                        f'<div class="who">{E(t["agent"] or t["role"])} · <span class="st {E(t["status"])}">{E(STATUS_AR.get(t["status"], t["status"]))}</span>'
                        f'{" · محاولات " + str(t["attempts"]) if t["attempts"] > 1 else ""}</div></div>' for t in P["tasks"])
        warn = "".join(f'<div class="warn">⚠️ {E(x)}</div>' for x in P.get("integrity", []))
        projs.append(f'<div class="proj"><div class="head" style="display:flex;gap:10px;flex-wrap:wrap;align-items:baseline">'
                     f'<h3>مشروع {E(P["id"])}</h3><span class="st {E(P["status"])}">{E(STATUS_AR.get(P["status"], P["status"]))}</span>'
                     f'<span class="mut num" style="font-size:12px">{P["tokens"]:,} توكن · {E(P["created"][:16].replace("T", " "))}</span></div>'
                     f'<div class="req">{E(P["request"][:300])}</div><div class="flow">{steps}</div>{warn}'
                     + (f'<div class="summary">{E(P["summary"][:1200])}</div>' if P["summary"] else "") + "</div>")
    # ---------- الخط الزمني ----------
    keep = [e for e in d["audit"] if e.get("event") in EVENT_AR]
    tl = []
    for e in keep[-40:][::-1]:
        ev = e["event"]
        det = ""
        if ev == "task":
            det = f'{e.get("project")}/{e.get("task")} · {e.get("agent")} · {STATUS_AR.get(e.get("status"), e.get("status"))}'
        elif ev == "planned":
            det = f'{e.get("project")}: ' + "، ".join(f"{a}→{b}" for a, b in e.get("tasks", []))
        elif ev == "request":
            det = f'{e.get("project")}: {str(e.get("text", ""))[:90]}'
        elif ev == "hired":
            det = f'{e.get("role")}'
        elif ev == "final_test_opened":
            try:
                c = json.loads(e.get("content", "{}"))
                det = f'{e.get("project")} · {c.get("strategy")} · نجح بفحص المخاطر: {"نعم" if c.get("final_check", {}).get("passed") else "لا"}'
            except ValueError:
                det = e.get("project", "")
        elif ev in ("approval_requested", "approval"):
            det = f'{e.get("id", "")} {e.get("action", "")} {e.get("details", "")}'[:120]
        elif ev == "tamper_restored":
            det = "، ".join(os.path.basename(f) for f in e.get("files", []))
        elif ev == "lab_trial":
            det = f'{e.get("name")} · {e.get("agent")} · {e.get("verdict")}'
        elif ev == "lab_daily":
            det = f'أيام مستقبل: {e.get("forward_days")} · استراتيجيات تحت الاختبار: {e.get("active")}'
        elif ev == "skill_saved":
            det = e.get("name", "")
        tl.append(f'<li class="{"bad" if ev in ("integrity_violation", "task_error", "refusal") else ""}">'
                  f'<time>{E(e.get("t", "")[5:16])}</time><b>{E(EVENT_AR[ev])}</b> <span class="mut">{E(det)}</span></li>')
    # ---------- مختبر الاستراتيجيات ----------
    labhtml = ""
    try:
        from . import lab as _lab
        lb, lt = _lab.board(), _lab.trials()
    except Exception:
        lb, lt = {}, []
    if lb or lt:
        ST = {"forward": ("بالاختبار على المستقبل", "done"), "rejected": ("انرفضت", "failed"), "waitlist": ("بالدور", "pending"),
              "error": ("خطأ بالكود", "failed"), "promoted": ("نجحت", "done")}
        rows = []
        for k, v in sorted(lb.items(), key=lambda kv: (kv[1].get("status") != "forward", kv[1].get("submitted", "")), reverse=False):
            f, va = v.get("forward") or {}, v.get("val") or {}
            fw = (f'{f.get("days", 0)} يوم · {f.get("return", 0):+.2%} مقابل {f.get("buy_hold", 0):+.2%}' if v.get("status") == "forward" else "—")
            lab_, cls = ST.get(v.get("status"), (v.get("status"), ""))
            rows.append(f'<tr><td><b>{E(k)}</b><div class="mut" style="font-size:12px">{E((v.get("hypothesis") or "")[:110])}</div></td>'
                        f'<td class="num">{E(str(va.get("sharpe", "—")))}<span class="mut"> / {E(str(va.get("bh_sharpe", "—")))}</span></td>'
                        f'<td><span class="st {cls}">{E(lab_)}</span><div class="mut" style="font-size:12px">{E("; ".join(v.get("reasons") or [])[:120])}</div></td>'
                        f'<td class="num">{E(fw)}</td><td>{E(v.get("agent", ""))}</td></tr>')
        labhtml = (f'<h2>مختبر الاستراتيجيات</h2><p class="mut" style="max-width:70ch">الايجنت بيخترعوا أفكار، والمدينة بتقيّمها بكود ثابت جوا Docker. '
                   f'اللي بتنجح بتنختبر على أيام جديدة ما حدا شافها. <b class="num">{len(lt)}</b> محاولة لحد هلأ؛ كل ما زادت المحاولات زاد احتمال نجاح بالصدفة، '
                   f'فالحكم الحقيقي هو عمود "المستقبل".</p><div class="box" style="overflow-x:auto;padding:0"><table style="width:100%;border-collapse:collapse;font-size:13px">'
                   f'<thead><tr style="text-align:right"><th style="padding:8px">الفكرة</th><th>Sharpe تحقق / شراء واحتفاظ</th><th>الحالة</th><th>المستقبل</th><th>مين</th></tr></thead>'
                   f'<tbody>{"".join(rows)}</tbody></table></div>')
    skills = "".join(f"<li>{E(s[:140])}</li>" for s in d["skills"]) or "<li class='mut'>ولا وحدة لسا</li>"
    lessons = "".join(f"<li>{E(l[:200])}</li>" for l in st["lessons"]) or "<li class='mut'>ولا درس لسا</li>"
    llm = f'<span><b>{d["llm_n"]}</b> طلب للعقل</span>' if d["llm_n"] else ""
    head = ('<title>Agent City</title><meta name="claude:viewport-fit-sides" content="cover">'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+Arabic:wght@400;600&family=Readex+Pro:wght@500;600&display=swap">'
            f'<style>{CSS}</style>')
    body = (f'<div dir="rtl" lang="ar"><header class="sky"><div class="wrap"><h1>مدينتك: Agent City</h1>'
            f'<p class="lede">شركة ايجنت مستقلة. انت بتحكي مع المدير، والمدير بيوزع الشغل على الفريق. كل بناية ايجنت، '
            f'وكل شباك مضوي استعمال أداة حقيقي من سجل التدقيق.</p>'
            f'<div class="stats"><span><b>{len(agents)}</b> ايجنت</span><span><b>{len(projects)}</b> مشاريع</span>'
            f'<span><b>{sum(t["status"] == "done" for t in tasks)}/{len(tasks)}</b> مهمة خلصت</span>'
            f'<span><b>{total_tools}</b> استعمال أداة</span><span><b>{tokens:,}</b> توكن</span>{llm}</div>'
            f'<div class="skyline">{"".join(sky)}</div>'
            f'<div class="legend"><span><i style="background:var(--win)"></i>شباك مضوي = استعمال أداة</span>'
            f'<span><i style="background:var(--win-off)"></i>طابق فاضي</span><span>طول البناية حسب كمية الشغل</span></div>'
            f'</div><div class="street"></div></header><main class="wrap">'
            f'<h2>هيكل الشركة</h2>{org}'
            f'<h2>الفريق</h2><div class="cards">{"".join(cards)}</div>'
            f'{labhtml}<h2>المشاريع</h2>{"".join(projs) or "<p class=mut>ما في مشاريع لسا.</p>"}'
            f'<div class="two" style="margin-top:28px"><div class="box"><h3 style="margin-bottom:8px">مهارات المدينة</h3><ul>{skills}</ul></div>'
            f'<div class="box"><h3 style="margin-bottom:8px">دروس الشركة</h3><ul>{lessons}</ul></div></div>'
            f'<h2>شو صار مؤخراً</h2><ul class="tl">{"".join(tl) or "<li class=mut>ولا شي لسا</li>"}</ul>'
            f'<footer>الصلاحيات الملونة: <span class="chip danger">بحتاج موافقتك</span> <span class="chip box">معزول بـ Docker</span> '
            f'<span class="chip net">وصول إنترنت</span> · مولّدة من state.json وaudit.jsonl</footer></main></div>')
    page = head + body
    if fragment:
        return page
    return f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{page.replace("</style>", "</style></head><body>", 1)}</body></html>'
