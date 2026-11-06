"""الحالة الدائمة للمدينة: state.json + سجل تدقيق + مفتاح إيقاف طوارئ."""
import copy, hashlib, json, os, shutil, time

SEED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "seed")
WORK = ["read_file", "write_file", "list_files", "list_skills", "load_skill", "save_skill", "request_approval"]

DEFAULT_AGENTS = {
    "researcher": {"role": "researcher", "tools": WORK + ["fetch_url"],
                   "instructions": "You research topics rigorously, compare sources, and write findings to files."},
    "engineer": {"role": "engineer", "tools": WORK + ["run_python", "shell"],
                 "instructions": "You write and TEST code. Never claim code works before running it."},
    "analyst": {"role": "analyst", "tools": WORK + ["run_python", "fetch_url"],
                "instructions": "You analyze data and run experiments with strict methodology (no data leakage)."},
    "writer": {"role": "writer", "tools": WORK,
               "instructions": "You write clear reports and documentation from the team's outputs."},
    "qa": {"role": "qa", "tools": ["read_file", "list_files", "run_python", "list_skills", "load_skill"],
           "instructions": "You independently verify deliverables by reading files and running code. Be strict."},
}


def home():
    return os.path.abspath(os.getenv("CITY_HOME", "city_home"))


def path(*a):
    return os.path.join(home(), *a)


def init():
    os.makedirs(path("skills"), exist_ok=True)
    os.makedirs(path("workspace"), exist_ok=True)
    shared = path("workspace", "shared")
    if not os.path.exists(shared) and os.path.isdir(os.path.join(SEED, "shared")):
        shutil.copytree(os.path.join(SEED, "shared"), shared)
    sk = os.path.join(SEED, "skills")
    if os.path.isdir(sk):
        for f in os.listdir(sk):
            if not os.path.exists(path("skills", f)):
                shutil.copy(os.path.join(sk, f), path("skills", f))


def load():
    if not os.path.exists(path("state.json")):
        return {"projects": {}, "agents": copy.deepcopy(DEFAULT_AGENTS), "approvals": {}, "lessons": [], "seq": 0}
    return json.load(open(path("state.json"), encoding="utf-8"))


def save(st):
    tmp = path("state.json.tmp")
    json.dump(st, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, path("state.json"))


def audit(event, **kw):
    with open(path("audit.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.strftime("%F %T"), "event": event, **kw}, ensure_ascii=False) + "\n")


def killed():
    return os.path.exists(path("STOP"))


# ---------- ملفات محمية: أدوات المدينة الأساسية (مثل risk.py) ما بيقدر أي ايجنت يعدّلها ----------
def _seed_shared():
    base = os.path.join(SEED, "shared")
    for d, _, fs in os.walk(base):
        for f in fs:
            if not f.endswith(".pyc"):
                src = os.path.join(d, f)
                yield src, path("workspace", "shared", os.path.relpath(src, base))


def is_protected(full):
    full = os.path.abspath(full)
    return any(os.path.abspath(dst) == full for _, dst in _seed_shared())


def _h(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def verify_protected():
    """لو كود مولّد غيّر ملف محمي (run_python مش sandbox)، بنرجّعه من الـ seed وبنسجّل بالتدقيق."""
    fixed = []
    for src, dst in _seed_shared():
        if _h(src) != _h(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(src, dst)
            fixed.append(os.path.relpath(dst, home()))
    if fixed:
        audit("tamper_restored", files=fixed)
    return fixed


# ---------- طابور الأوامر (ويب/CLI) + قفل المشغّل ----------
# أي قرار (موافقة/رفض/طلب جديد) بينكتب بطابور. اللي بيطبّقه هو المشغّل (run/serve) إذا شغال،
# أو العملية نفسها إذا ما في مشغّل. هيك ما في عمليتين بيكتبوا state.json فوق بعض.
import fcntl


def enqueue(kind, **data):
    with open(path("inbox.jsonl"), "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps({"t": time.strftime("%F %T"), "kind": kind, **data}, ensure_ascii=False) + "\n")
    audit("enqueued", kind=kind, **data)


def drain():
    p = path("inbox.jsonl")
    if not os.path.exists(p):
        return []
    with open(p, "r+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        items = [json.loads(l) for l in f if l.strip()]
        f.seek(0); f.truncate()
    return items


def runner_alive():
    try:
        pid = int(open(path("RUNNER")).read().strip())
        if pid == os.getpid():
            return False
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def claim_runner():
    if runner_alive():
        raise SystemExit("في مشغّل ثاني شغال للمدينة (run/serve). استنى يخلص أو أوقفه.")
    open(path("RUNNER"), "w").write(str(os.getpid()))


def release_runner():
    try:
        if int(open(path("RUNNER")).read().strip()) == os.getpid():
            os.remove(path("RUNNER"))
    except (OSError, ValueError):
        pass
