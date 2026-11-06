import argparse, sys
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
