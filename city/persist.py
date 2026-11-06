"""ذاكرة المدينة على GitHub: city_state/ بالريبو (الحالة، التدقيق، المهارات، المختبر، البيانات المجمّدة وأيام المستقبل).
city_home مؤقت على أي جهاز؛ city_state هو اللي بيضل. export بعد كل جولة، import بأول جولة على جهاز جديد."""
import os, shutil
from . import store

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DST = os.path.join(REPO, "city_state")
ITEMS = ["state.json", "audit.jsonl", "skills", "lab", "workspace/shared/data", "workspace/p*"]
SKIP = ("__pycache__", "_run.py", ".tmp")


def _copy(src, dst):
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True, ignore=lambda d, fs: [f for f in fs if f.endswith(SKIP) or f in SKIP])
    elif os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def _items(root):
    import glob
    out = []
    for it in ITEMS:
        out += [os.path.relpath(p, root) for p in glob.glob(os.path.join(root, it))]
    return out


def export_state():
    os.makedirs(DST, exist_ok=True)
    items = _items(store.home())
    for rel in items:
        _copy(store.path(rel), os.path.join(DST, rel))
    return f"exported {len(items)} items to city_state/"


def import_state():
    if not os.path.isdir(DST):
        return "no city_state/ in repo; starting fresh"
    if os.path.exists(store.path("state.json")) and os.path.getmtime(store.path("state.json")) > \
            os.path.getmtime(os.path.join(DST, "state.json")):
        return "city_home is newer than city_state/; not overwriting"
    items = _items(DST)
    for rel in items:
        _copy(os.path.join(DST, rel), store.path(rel))
    store.verify_protected()
    return f"imported {len(items)} items from city_state/"
