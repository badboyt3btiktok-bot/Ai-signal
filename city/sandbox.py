"""تشغيل كود الايجنت معزول داخل Docker.
- بدون شبكة (CITY_SANDBOX_NET=none افتراضياً)، rootfs للقراءة فقط، بدون capabilities، حدود ذاكرة/CPU/عمليات.
- مجلد المشروع بس قابل للكتابة (/work)، والمكتبات المشتركة (shared/ وفيها risk.py) للقراءة فقط (/shared).
- CITY_SANDBOX: auto (Docker إذا الصورة جاهزة، وإلا تشغيل محلي مع تحذير) | docker (إجباري، بدون fallback) | local.
"""
import os, shutil, subprocess, uuid

IMAGE = os.getenv("CITY_SANDBOX_IMAGE", "agentcity-sandbox:1")
DOCKERFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sandbox")
_ready = None


def mode():
    return os.getenv("CITY_SANDBOX", "auto").lower()


_checked = 0.0


def available(refresh=False):
    """Docker شغال والصورة موجودة؟ النتيجة السلبية ما بتنحفظ للأبد: بنعيد الفحص كل 30 ثانية
    (لو Docker رجع يشتغل بنص الجولة، الكود الجاي بيرجع ينعزل)."""
    global _ready, _checked
    import time
    if _ready is None or refresh or (not _ready and time.time() - _checked > 30):
        _checked = time.time()
        try:
            _ready = bool(shutil.which("docker")) and subprocess.run(
                ["docker", "image", "inspect", IMAGE], capture_output=True, timeout=20).returncode == 0
        except Exception:
            _ready = False
    return _ready


def use_docker():
    """True = Docker, False = محلي. بيرمي خطأ إذا الوضع docker إجباري والـ sandbox مش جاهز."""
    m = mode()
    if m == "local":
        return False
    if available():
        return True
    if m == "docker":
        raise RuntimeError(f"sandbox غير جاهز ({IMAGE}). شغّل: python agentcity.py sandbox")
    return False


def build(ca=None):
    """بيبني الصورة. ca: شهادة proxy اختيارية (بتنمرر كـ secret، مش بالصورة)."""
    ca = ca or os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE")
    cmd = ["docker", "build", "-t", IMAGE]
    if ca and os.path.exists(ca):
        cmd += ["--secret", f"id=ca,src={ca}"]
    r = subprocess.run(cmd + [DOCKERFILE_DIR], capture_output=True, text=True)
    available(refresh=True)
    return r.returncode, (r.stdout + r.stderr)[-3000:]


def _user(workdir):
    """نشغّل كمستخدم عادي. إذا المدينة شغالة كـ root، بنعطي مجلد المشروع للمستخدم 10001 بدل ما نشغّل root بالحاوية."""
    if os.getuid() != 0:
        return f"{os.getuid()}:{os.getgid()}"
    for d, ds, fs in os.walk(workdir):
        for x in [d] + [os.path.join(d, f) for f in fs]:
            try:
                os.chown(x, 10001, 10001)
            except OSError:
                pass
    return "10001:10001"


def command(argv, workdir, shared):
    name = f"city-{uuid.uuid4().hex[:12]}"
    cmd = ["docker", "run", "--rm", "--name", name,
           "--network", os.getenv("CITY_SANDBOX_NET", "none"),
           "--memory", os.getenv("CITY_SANDBOX_MEM", "2g"), "--cpus", os.getenv("CITY_SANDBOX_CPUS", "2"),
           "--pids-limit", "256", "--read-only", "--tmpfs", "/tmp:rw,size=256m",
           "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
           "-u", _user(workdir),
           "-v", f"{os.path.abspath(workdir)}:/work:rw", "-v", f"{os.path.abspath(shared)}:/shared:ro",
           "-w", "/work", "-e", "PYTHONPATH=/shared", "-e", "HOME=/work", "-e", "PYTHONIOENCODING=utf-8",
           "-e", "MPLCONFIGDIR=/tmp", IMAGE] + list(argv)
    return name, cmd


def run(argv, workdir, shared, timeout):
    name, cmd = command(argv, workdir, shared)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True)
        return None, "ERROR: timeout"
