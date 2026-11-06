"""أدوات الايجنت. كل ايجنت بياخد فقط الأدوات المسموحة لدوره. الأفعال الخطرة (shell) لازم موافقتك."""
import os, re, subprocess, sys, urllib.request
from . import sandbox, store


class Ctx:
    def __init__(self, st, project, task, agent):
        self.st, self.project, self.task, self.agent = st, project, task, agent
        self.root = store.path("workspace")
        self.workdir = os.path.join(self.root, project["id"])
        os.makedirs(self.workdir, exist_ok=True)
        self.blocked, self.block_reason = False, ""


def _safe(ctx, rel, write=False):
    full = os.path.abspath(os.path.join(ctx.workdir, rel))
    roots = [ctx.workdir, os.path.join(ctx.root, "shared")] if write else [ctx.root]
    if not any(full == r or full.startswith(r + os.sep) for r in roots):
        raise PermissionError("المسار خارج الصلاحيات المسموحة")
    return full


def read_file(ctx, a):
    with open(_safe(ctx, a["path"]), encoding="utf-8", errors="replace") as f:
        return f.read()[:20000]


def write_file(ctx, a):
    p = _safe(ctx, a["path"], write=True)
    if store.is_protected(p):
        raise PermissionError("هذا ملف محمي من المدينة (أدوات المخاطر/الباكتست الأساسية). أضف ملف جديد بدل التعديل عليه.")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    append = str(a.get("append", "")).lower() in ("true", "1", "yes")
    with open(p, "a" if append else "w", encoding="utf-8") as f:
        f.write(a["content"])
    return f"{'appended' if append else 'wrote'} {len(a['content'])} chars to {a['path']}"


def list_files(ctx, a):
    base = _safe(ctx, a.get("path", "."))
    out = []
    for d, _, fs in os.walk(base):
        for f in fs:
            out.append(os.path.relpath(os.path.join(d, f), ctx.workdir))
    return "\n".join(sorted(out)[:200]) or "(empty)"


# متغيرات شبكة/شهادات بتنمرر للكود المولّد (بدونها أي تحميل بيانات بيفشل خلف proxy). مفاتيح الـ API ما بتنمرر.
PASS_ENV = ("HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR",
            "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "LANG", "LC_ALL", "TZ")


def _env(ctx):
    env = {k: os.environ[k] for k in PASS_ENV if k in os.environ}
    env.update({"PATH": os.environ.get("PATH", ""), "HOME": ctx.workdir, "PYTHONIOENCODING": "utf-8",
                "PYTHONPATH": os.path.join(ctx.root, "shared")})  # بدون مفتاح API
    return env


TIMEOUT = int(os.getenv("CITY_RUN_TIMEOUT", "300"))
_warned = False


def _exec(argv, ctx, timeout=None, shell=False):
    """argv = أمر مكتوب بمسارات الحاوية (/work, /shared). Docker إذا متاح، وإلا محلي (مع تحذير)."""
    global _warned
    timeout = timeout or TIMEOUT
    shared = os.path.join(ctx.root, "shared")
    if sandbox.use_docker():
        code, out = sandbox.run(["sh", "-c", argv] if shell else argv, ctx.workdir, shared, timeout)
        return out if code is None else f"exit={code}\n{out[-6000:]}"
    note = ""
    if not _warned:
        _warned = True
        store.audit("sandbox_unavailable", mode=sandbox.mode())
        note = "[warning: running WITHOUT Docker sandbox]\n"
    host = {"/work": ctx.workdir, "/shared": shared}
    if shell:
        cmd = argv
    else:
        cmd = [sys.executable if a == "python" else next(
            (h + a[len(k):] for k, h in host.items() if a == k or a.startswith(k + "/")), a) for a in argv]
    try:
        r = subprocess.run(cmd, cwd=ctx.workdir, capture_output=True, text=True,
                           timeout=timeout, env=_env(ctx), shell=shell)
        return f"{note}exit={r.returncode}\n{(r.stdout + r.stderr)[-6000:]}"
    except subprocess.TimeoutExpired:
        return "ERROR: timeout"


def _in_box(ctx, full):
    """مسار بالحاوية للملف: مجلد المشروع -> /work، المكتبات المشتركة -> /shared."""
    for root, mnt in ((ctx.workdir, "/work"), (os.path.join(ctx.root, "shared"), "/shared")):
        if full == root or full.startswith(root + os.sep):
            return mnt + full[len(root):].replace(os.sep, "/")
    raise PermissionError("run_python بيشغّل بس ملفات من مجلد مشروعك أو shared/")


def run_python(ctx, a):
    if a.get("code"):
        target = os.path.join(ctx.workdir, "_run.py")
        open(target, "w", encoding="utf-8").write(a["code"])
    else:
        target = _safe(ctx, a["path"])
    return _exec(["python", _in_box(ctx, target)], ctx)


def fetch_url(ctx, a):
    req = urllib.request.Request(a["url"], headers={"User-Agent": "AgentCity/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read(60000).decode("utf-8", "replace")


def _approval(ctx, action, details):
    ap = ctx.st["approvals"]
    for a in ap.values():
        if a["project"] == ctx.project["id"] and a["action"] == action and a["details"] == details:
            if a["status"] == "approved" and not a["used"]:
                a["used"] = True
                return "approved"
            if a["status"] == "denied":
                return "denied"
            if a["status"] == "pending":
                ctx.blocked, ctx.block_reason = True, f"بانتظار موافقة المالك ({a['id']}): {action} {details}"
                return "pending"
    aid = f"a{len(ap) + 1}"
    ap[aid] = {"id": aid, "project": ctx.project["id"], "task": ctx.task["id"], "agent": ctx.agent,
               "action": action, "details": details, "status": "pending", "used": False}
    ctx.blocked, ctx.block_reason = True, f"بانتظار موافقة المالك ({aid}): {action} {details}"
    store.audit("approval_requested", id=aid, action=action, details=details)
    return "pending"


def shell(ctx, a):
    s = _approval(ctx, "shell", a["command"])
    if s == "approved":
        return _exec(a["command"], ctx, shell=True)
    if s == "denied":
        return "DENIED by owner. Find an alternative approach."
    return "BLOCKED: waiting for owner approval. Stop working on this task and summarize progress."


def request_approval(ctx, a):
    s = _approval(ctx, a["action"], a.get("details", ""))
    return {"approved": "APPROVED. Proceed.", "denied": "DENIED. Choose another approach.",
            "pending": "BLOCKED: waiting for owner approval. Stop and summarize progress."}[s]


def _slug(n):
    return re.sub(r"[^a-z0-9_-]", "_", n.lower())[:60]


def save_skill(ctx, a):
    if store.seed_skill(_slug(a["name"])):
        raise PermissionError("هاي مهارة أساسية للمدينة وما بتنكتب فوقها. احفظها باسم جديد.")
    p = store.path("skills", _slug(a["name"]) + ".md")
    open(p, "w", encoding="utf-8").write(f"description: {a['description']}\n# {a['name']}\n{a['content']}\n")
    store.audit("skill_saved", agent=ctx.agent, name=a["name"])
    return f"skill '{a['name']}' saved for the whole city"


def skill_index():
    d, out = store.path("skills"), []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        first = open(os.path.join(d, f), encoding="utf-8").readline().strip()
        out.append(f"- {f[:-3]}: {first.replace('description: ', '')}")
    return "\n".join(out) or "(none yet)"


def list_skills(ctx, a):
    return skill_index()


def load_skill(ctx, a):
    return open(store.path("skills", _slug(a["name"]) + ".md"), encoding="utf-8").read()[:15000]


def S(**p):
    return {"type": "object", "properties": {k: {"type": "string", "description": v} for k, v in p.items()},
            "required": list(p)}


ALL = {
    "read_file": ("Read a text file from the workspace.", S(path="relative path"), read_file),
    "write_file": ("Write a file in your project workspace. For big files call it several times with append='true'.",
                   {"type": "object", "properties": {"path": {"type": "string", "description": "relative path"},
                                                     "content": {"type": "string", "description": "file content"},
                                                     "append": {"type": "string", "description": "'true' to append"}},
                    "required": ["path", "content"]}, write_file),
    "list_files": ("List files in the workspace.", {"type": "object", "properties": {"path": {"type": "string"}}}, list_files),
    "run_python": ("Run Python code (or a file) in your project workspace. Provide code OR path.",
                   {"type": "object", "properties": {"code": {"type": "string"}, "path": {"type": "string"}}}, run_python),
    "fetch_url": ("HTTP GET a URL (read-only).", S(url="full URL"), fetch_url),
    "shell": ("Run a shell command. REQUIRES owner approval for each distinct command.", S(command="command"), shell),
    "request_approval": ("Ask the owner to approve an irreversible/external action (spend, send, deploy, delete).",
                         S(action="short action name", details="exact details"), request_approval),
    "save_skill": ("Save a reusable procedure so every agent in the city can use it later.",
                   S(name="skill name", description="one line", content="markdown how-to"), save_skill),
    "list_skills": ("List skills the city has learned.", {"type": "object", "properties": {}}, list_skills),
    "load_skill": ("Read a skill by name.", S(name="skill name"), load_skill),
}


def schemas(names):
    return [{"name": n, "description": ALL[n][0], "input_schema": ALL[n][1]} for n in names]


def call(ctx, name, args, allowed):
    if name not in allowed:
        return f"ERROR: tool '{name}' is not permitted for your role"
    return ALL[name][2](ctx, args or {})
