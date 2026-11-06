"""مختبر الاستراتيجيات: الايجنت بيقدّموا أفكار كملفات كود، والمدينة (مش الايجنت) بتقيّمها وبتحفظ النتائج.

- التقييم: gold_toolkit/lab_harness.py جوا Docker (بدون شبكة). الاختيار على التدريب، نظرة وحدة على التحقق، فحص نظر للمستقبل.
- كل محاولة بتنعدّ (trials.jsonl) وفي حد يومي، لأن كتر المحاولات على نفس البيانات بيصنع نتائج حلوة بالصدفة.
- اللي بيعدّي risk.check بيدخل "اختبار المستقبل": كل يوم المدينة بتنزّل الأيام الجديدة وبتسجّل إشارات الاستراتيجية
  عليها مقابل الشراء والاحتفاظ. هاد الحكم الصادق الوحيد، لأن ولا ايجنت شاف هالأيام وقت البحث.
- الملفات بـ city_home/lab/ (برّا workspace)، فالايجنت ما بيقدروا يعدّلوا النتائج.
"""
import datetime, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from . import sandbox, store

MAX_PER_DAY = int(os.getenv("CITY_LAB_MAX_PER_DAY", "12"))
MAX_FORWARD = int(os.getenv("CITY_LAB_MAX_FORWARD", "10"))
TIMEOUT = 600


def d(*a):
    p = store.path("lab", *a)
    os.makedirs(os.path.dirname(p) if a and "." in a[-1] else p, exist_ok=True)
    return p


def _toolkit():
    store.verify_protected()                            # لازم قبل الاستيراد، وإلا بنستورد نسخة قديمة من الأدوات
    sh = store.path("workspace", "shared")
    if sh not in sys.path:
        sys.path.insert(0, sh)
    import gold_toolkit.data as gd
    return gd


def board():
    p = d("board.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def save_board(b):
    tmp = d("board.json.tmp")
    json.dump(b, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, d("board.json"))


def trials():
    p = d("trials.jsonl")
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []


def _run(strategy_file, args):
    """شغّل المقيّم الثابت على ملف استراتيجية (Docker إذا متاح). بيرجّع dict النتيجة."""
    store.verify_protected()
    shared = store.path("workspace", "shared")
    box = tempfile.mkdtemp(prefix="lab-")
    try:
        shutil.copy(strategy_file, os.path.join(box, "strat.py"))
        if sandbox.use_docker():
            code, out = sandbox.run(["python", "/shared/gold_toolkit/lab_harness.py", args[0], "/work/strat.py"] + args[1:],
                                    box, shared, TIMEOUT)
        else:
            store.audit("sandbox_unavailable", where="lab")
            r = subprocess.run([sys.executable, os.path.join(shared, "gold_toolkit", "lab_harness.py"), args[0],
                                os.path.join(box, "strat.py")] + args[1:], capture_output=True, text=True, timeout=TIMEOUT,
                               env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": shared, "HOME": box}, cwd=box)
            out = r.stdout + r.stderr
        m = re.findall(r"^LAB_RESULT (.*)$", out or "", re.M)
        return json.loads(m[-1]) if m else {"verdict": "error", "error": (out or "no output")[-800:]}
    finally:
        shutil.rmtree(box, ignore_errors=True)


def _last_date():
    gd = _toolkit()
    return str(gd.full().index[-1].date())


def submit(src, name, agent="owner", project="", hypothesis=""):
    today = datetime.date.today().isoformat()
    n_today = sum(1 for t in trials() if t["t"][:10] == today)
    if n_today >= MAX_PER_DAY:
        return {"verdict": "error", "error": f"daily trial limit reached ({MAX_PER_DAY}). Many trials on the same data "
                                             "produce lucky results; think harder about fewer ideas."}
    slug = re.sub(r"[^a-z0-9_]", "_", name.lower())[:40].strip("_") or "strategy"
    b = board()
    base, k = slug, 2
    while slug in b or os.path.exists(d("strategies", slug + ".py")):
        slug, k = f"{base}_v{k}", k + 1
    dst = d("strategies", slug + ".py")
    shutil.copy(src, dst)                                   # نسخة مجمّدة: اللي انقيّم هو اللي بينحفظ
    sha = hashlib.sha256(open(dst, "rb").read()).hexdigest()[:16]
    res = _run(dst, ["evaluate"])
    rec = {"t": datetime.datetime.now().isoformat(timespec="seconds"), "name": slug, "agent": agent, "project": project,
           "sha": sha, **{k: res.get(k) for k in ("verdict", "params", "train", "val", "reasons", "combos", "error")}}
    with open(d("trials.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    entry = {"status": res.get("verdict"), "agent": agent, "project": project, "submitted": rec["t"], "sha": sha,
             "hypothesis": (hypothesis or res.get("hypothesis") or "")[:500], "params": res.get("params"),
             "train": res.get("train"), "val": res.get("val"), "reasons": res.get("reasons") or ([res["error"]] if res.get("error") else [])}
    if res.get("verdict") == "promoted":
        active = [k for k, v in b.items() if v.get("status") == "forward"]
        if len(active) >= MAX_FORWARD:
            entry["status"] = "waitlist"
        else:
            entry["status"] = "forward"
            entry["since"] = _last_date()                   # بس الأيام اللي بعد هلأ بتنحسب
            entry["forward"] = {"days": 0, "return": 0.0, "buy_hold": 0.0, "trades": 0}
    b[slug] = entry
    save_board(b)
    store.audit("lab_trial", name=slug, agent=agent, verdict=entry["status"])
    res["name"], res["status"] = slug, entry["status"]
    return res


def daily():
    """(المدينة) نزّل الأيام الجديدة وحدّث اختبار المستقبل لكل استراتيجية مرشحة."""
    gd = _toolkit()
    try:
        n = gd.update_forward()
    except Exception as e:
        n = None
        store.audit("forward_update_error", error=str(e)[:300])
    b = board()
    for k, v in b.items():
        if v.get("status") != "forward":
            continue
        r = _run(d("strategies", k + ".py"), ["forward", json.dumps(v["params"]), v["since"]])
        if r.get("verdict") == "error":
            v["forward_error"] = r.get("error")
            continue
        series = r.pop("series", [])
        v["forward"] = r
        json.dump(series, open(d("forward", k + ".json"), "w"), ensure_ascii=False)
    save_board(b)
    store.audit("lab_daily", forward_days=n, active=sum(v.get("status") == "forward" for v in b.values()))
    return {"forward_days": n, "board": b}


def summary(limit=15):
    b, ts = board(), trials()
    lines = [f"Total trials so far: {len(ts)} (today {sum(1 for t in ts if t['t'][:10] == datetime.date.today().isoformat())}"
             f"/{MAX_PER_DAY}). More trials => higher chance of lucky validation results; forward test is the real judge."]
    fw = [(k, v) for k, v in b.items() if v.get("status") == "forward"]
    lines.append(f"\nFORWARD TEST ({len(fw)}/{MAX_FORWARD} active):")
    for k, v in fw:
        f = v.get("forward", {})
        lines.append(f"- {k} {v.get('params')} since {v.get('since')}: {f.get('days', 0)} days, "
                     f"ret {f.get('return', 0):+.2%} vs buy&hold {f.get('buy_hold', 0):+.2%}, now {'LONG' if f.get('position_now') else 'flat'}")
    rej = sorted([(k, v) for k, v in b.items() if v.get("status") == "rejected"], key=lambda kv: kv[1]["submitted"])[-limit:]
    lines.append("\nRECENT REJECTIONS (learn from these):")
    for k, v in rej:
        lines.append(f"- {k}: {'; '.join(v.get('reasons') or [])[:220]} | hyp: {v.get('hypothesis', '')[:120]}")
    return "\n".join(lines)
