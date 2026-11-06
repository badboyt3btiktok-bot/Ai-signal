import argparse, json, os, sys
from city import store
from city.city import City

p = argparse.ArgumentParser(description="Agent City: شركة ايجنت مستقلة")
sub = p.add_subparsers(dest="cmd", required=True)
a = sub.add_parser("add", help="طلب جديد للمدير"); a.add_argument("text", nargs="?"); a.add_argument("--file")
sub.add_parser("run", help="شغّل كل الطلبات المعلقة")
d = sub.add_parser("serve", help="وضع مستمر: المدينة بتستنى طلباتك وبتشتغل لحالها"); d.add_argument("--interval", type=int, default=5)
sub.add_parser("status")
sub.add_parser("approvals")
for n in ("approve", "deny"):
    sub.add_parser(n).add_argument("id")
sub.add_parser("agents"); sub.add_parser("skills")
sub.add_parser("stop", help="مفتاح إيقاف طوارئ"); sub.add_parser("resume")
sub.add_parser("sandbox", help="ابني صورة Docker لعزل كود الايجنت")
dd = sub.add_parser("data", help="نزّل بيانات الذهب الحقيقية (GC=F) وجمّدها لكل الفريق")
dd.add_argument("--refresh", action="store_true", help="تحديث النسخة المجمّدة (بيغيّر train/val/test لأي مشروع شغال!)")
LB = sub.add_parser("lab", help="مختبر الاستراتيجيات: board | daily | submit FILE")
LB.add_argument("action", choices=["board", "daily", "submit"]); LB.add_argument("file", nargs="?"); LB.add_argument("--name")
sub.add_parser("research-day", help="جولة بحث يومية: المختبر بيتحدّث، والمدير بيستلم مهمة بحث جديدة")
SS = sub.add_parser("state", help="احفظ/رجّع ذاكرة المدينة (city_state/ بالريبو)"); SS.add_argument("action", choices=["export", "import"])
V = sub.add_parser("view", help="ولّد صفحة HTML بتوريك المدينة والايجنت والمشاريع"); V.add_argument("--out", default="city.html")
L = sub.add_parser("llm", help="وضع CITY_BACKEND=file: اعرض الطلبات المعلقة أو رد عليها")
L.add_argument("action", choices=["show", "reply"]); L.add_argument("n", nargs="?", type=int)
L.add_argument("--file"); L.add_argument("--full", action="store_true")
w = sub.add_parser("web", help="واجهة ويب للمراقبة والموافقات من الموبايل")
w.add_argument("--host", default="127.0.0.1"); w.add_argument("--port", type=int, default=8787)
args = p.parse_args()

if args.cmd in ("stop", "resume"):
    store.init(); import os
    (open(store.path("STOP"), "w").close() if args.cmd == "stop" else os.path.exists(store.path("STOP")) and os.remove(store.path("STOP")))
    sys.exit(print("STOP مفعّل" if args.cmd == "stop" else "تم الاستئناف"))
if args.cmd == "sandbox":
    from city import sandbox
    code, out = sandbox.build()
    sys.exit(print(out, "\n" + ("الصورة جاهزة: " + sandbox.IMAGE if code == 0 else "فشل البناء")) or code)
if args.cmd == "data":
    store.init(); store.verify_protected()
    sys.path.insert(0, store.path("workspace", "shared"))
    from gold_toolkit import data
    s = data.from_yahoo(refresh=args.refresh)
    sys.exit(print(f"{len(s)} يوم ({s.index[0].date()} -> {s.index[-1].date()}) محفوظة بـ {data.CACHE}"))
if args.cmd == "llm":
    import glob, json, os
    store.init(); d = store.path("llm")
    pend = sorted(int(os.path.basename(f)[:-5]) for f in glob.glob(os.path.join(d, "inbox", "*.json")))
    if args.action == "show":
        if not pend:
            sys.exit(print("(ما في طلبات معلقة)"))
        n = args.n or pend[0]
        r = json.load(open(os.path.join(d, "inbox", f"{n}.json"), encoding="utf-8"))
        sysl = r["system"].splitlines()
        print(f"=== request {n} | {sysl[0][:160]} | tools: {[t['name'] for t in r['tools']]} | msgs={len(r['messages'])}")
        if args.full:
            print(r["system"])
        msgs = r["messages"] if args.full or len(r["messages"]) <= 2 else r["messages"][-1:]
        for m in msgs:
            cs = m["content"] if isinstance(m["content"], list) else [{"type": "text", "text": m["content"]}]
            for c in cs:
                if c["type"] == "text":
                    print(f"[{m['role']}] {c['text'][:6000]}")
                elif c["type"] == "tool_use":
                    print(f"[{m['role']} tool_use {c['id']}] {c['name']} {json.dumps(c['input'], ensure_ascii=False)[:1500]}")
                elif c["type"] == "tool_result":
                    print(f"[tool_result {c['tool_use_id']}{' ERROR' if c.get('is_error') else ''}] {str(c['content'])[:5000]}")
        sys.exit()
    n = args.n or (pend[0] if pend else None)
    body = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    json.loads(body)
    tmp = os.path.join(d, "outbox", f"{n}.json.tmp")
    open(tmp, "w", encoding="utf-8").write(body); os.replace(tmp, os.path.join(d, "outbox", f"{n}.json"))
    sys.exit(print(f"replied {n}"))
if args.cmd == "lab":
    store.init()
    from city import lab
    if args.action == "board":
        sys.exit(print(lab.summary()))
    if args.action == "daily":
        r = lab.daily(); sys.exit(print("أيام المستقبل:", r["forward_days"], "\n" + lab.summary()))
    r = lab.submit(args.file, args.name or os.path.basename(args.file)[:-3])
    sys.exit(print(json.dumps({k: r.get(k) for k in ("name", "status", "params", "val", "reasons", "error")}, ensure_ascii=False, indent=1)))
if args.cmd == "research-day":
    store.init()
    from city import lab
    lab.daily()
    c = City()
    if any(P["status"] in ("queued", "running") and P["request"].startswith("[RESEARCH DAY]") for P in c.st["projects"].values()):
        sys.exit(print("في جولة بحث لسا ما خلصت؛ ما ضفت وحدة جديدة."))
    day = sum(P["request"].startswith("[RESEARCH DAY]") for P in c.st["projects"].values()) + 1
    req = (f"[RESEARCH DAY] #{day}: continuous gold (GC=F daily) strategy research in the Strategy Lab. Signals only, no trading.\n"
           "Goal: find edges that beat buy & hold on risk-adjusted terms AND survive the live forward test.\n"
           "Plan at most 3 tasks: (1) review lab_board + company lessons and write ideas.md with 2-3 NEW, economically "
           "motivated hypotheses that differ from what was already tried (not parameter tweaks of rejected ideas); "
           "(2) implement each as a strategy module (HYPOTHESIS, small PARAMS grid <= 60 combos, causal signal(close, **p) -> 0/1) "
           "and submit with lab_submit (each idea ONE submission; never resubmit tweaks to chase validation); "
           "(3) write research_log.md: what was tried, lab verdicts, forward-test status of active strategies, honest conclusion.\n"
           "Rules: never evaluate the validation period yourself to tune; the lab does that once. Quality over quantity.\n\n"
           f"CURRENT LAB STATE:\n{lab.summary()}")
    sys.exit(print("جولة بحث جديدة:", c.add_request(req)))
if args.cmd == "state":
    store.init()
    from city import persist
    sys.exit(print(persist.export_state() if args.action == "export" else persist.import_state()))
if args.cmd == "view":
    store.init()
    from city import cityview
    open(args.out, "w", encoding="utf-8").write(cityview.render(fragment=False))
    sys.exit(print("انكتبت:", args.out))
if args.cmd == "web":
    from city import web
    sys.exit(web.serve(args.host, args.port))
c = City()
if args.cmd == "add":
    text = open(args.file, encoding="utf-8").read() if args.file else args.text
    if store.runner_alive():
        store.enqueue("request", text=text); print("تم، المشغّل الحالي رح يستلم الطلب.")
    else:
        print("تم، رقم المشروع:", c.add_request(text))
elif args.cmd == "run":
    c.run_all()
elif args.cmd == "serve":
    c.serve(args.interval)
elif args.cmd == "status":
    for P in c.st["projects"].values():
        print(f"\n[{P['id']}] {P['status']} | tokens={P['tokens']} | ~${P.get('cost_usd', 0)} | {P['request'][:70]}")
        for t in P["tasks"]:
            print(f"   {t['id']} {t['status']:<8} {t['agent'] or t['role']:<16} {t['title'][:50]}")
        for x in P.get("integrity", []):
            print("   ⚠️ ", x)
        if P["summary"]:
            print("   >>", P["summary"][:400])
elif args.cmd == "approvals":
    for x in c.st["approvals"].values():
        print(f"{x['id']} [{x['status']}] {x['agent']}@{x['project']}: {x['action']} -> {x['details']}")
elif args.cmd in ("approve", "deny"):
    store.enqueue("decision", id=args.id, ok=args.cmd == "approve")
    if store.runner_alive():
        print("تم، المشغّل الحالي رح يطبّق القرار.")
    else:
        City(); print("تم. شغّل: python agentcity.py run")
elif args.cmd == "agents":
    for n, s in c.st["agents"].items():
        print(f"{n}: tools={s['tools']}")
elif args.cmd == "skills":
    from city import tools; print(tools.skill_index())
