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
args = p.parse_args()

if args.cmd in ("stop", "resume"):
    store.init(); import os
    (open(store.path("STOP"), "w").close() if args.cmd == "stop" else os.path.exists(store.path("STOP")) and os.remove(store.path("STOP")))
    sys.exit(print("STOP مفعّل" if args.cmd == "stop" else "تم الاستئناف"))
c = City()
if args.cmd == "add":
    text = open(args.file, encoding="utf-8").read() if args.file else args.text
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
        if P["summary"]:
            print("   >>", P["summary"][:400])
elif args.cmd == "approvals":
    for x in c.st["approvals"].values():
        print(f"{x['id']} [{x['status']}] {x['agent']}@{x['project']}: {x['action']} -> {x['details']}")
elif args.cmd in ("approve", "deny"):
    c.decide(args.id, args.cmd == "approve"); print("تم. شغّل: python agentcity.py run")
elif args.cmd == "agents":
    for n, s in c.st["agents"].items():
        print(f"{n}: tools={s['tools']}")
elif args.cmd == "skills":
    from city import tools; print(tools.skill_index())
