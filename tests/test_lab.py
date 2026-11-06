"""مختبر الاستراتيجيات: تقييم بالمدينة (مش الايجنت)، كشف النظر للمستقبل، حدود المحاولات، اختبار المستقبل، حفظ الذاكرة."""
import json, os, shutil, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
REAL = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "city_home", "workspace", "shared", "data", "gold_GCF_daily.csv"))
os.environ["CITY_HOME"] = tempfile.mkdtemp()
import numpy as np, pandas as pd
from city import lab, store, tools
from city.city import City

store.init()
data_dir = store.path("workspace", "shared", "data"); os.makedirs(data_dir, exist_ok=True)
if os.path.exists(REAL):
    shutil.copy(REAL, data_dir)
else:                                                  # بدون بيانات حقيقية: سلسلة اصطناعية بنفس الصيغة
    rng = np.random.default_rng(3); n = 3000
    s = pd.Series(1200 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n))), index=pd.bdate_range("2014-11-06", periods=n))
    s.rename("close").rename_axis("date").to_csv(os.path.join(data_dir, "gold_GCF_daily.csv"))
c = City(); pid = c.add_request("lab test"); P = c.st["projects"][pid]
ctx = tools.Ctx(c.st, P, {"id": "t1"}, "analyst")
W = lambda name, code: tools.write_file(ctx, {"path": f"ideas/{name}.py", "content": code}) and f"ideas/{name}.py"

good = W("trend", 'HYPOTHESIS="trend"\nPARAMS={"lb":[60,120,250]}\ndef signal(close, lb):\n    return (close/close.shift(lb)-1>0).astype(float)\n')
cheat = W("cheat", 'PARAMS={"x":[1]}\ndef signal(close, x):\n    return (close.shift(-1)>close).astype(float).fillna(0)\n')
fullsample = W("zscore", 'PARAMS={"k":[1]}\ndef signal(close, k):\n    z=(close-close.mean())/close.std()\n    return (z<0).astype(float)\n')
short = W("short", 'PARAMS={"x":[1]}\ndef signal(close, x):\n    return close*0-1\n')
grid = W("grid", 'PARAMS={"a":list(range(100))}\ndef signal(close, a):\n    return close*0\n')

r = json.loads(tools.call(ctx, "lab_submit", {"path": good, "name": "trend", "hypothesis": "trends persist"}, c.st["agents"]["analyst"]["tools"]))
assert r["verdict"] in ("promoted", "rejected") and r.get("params") and r.get("val"), r
assert "lb" in r["params"]
for path, name, why in [(cheat, "cheat", "look-ahead"), (fullsample, "zscore", "look-ahead")]:
    r = lab.submit(store.path("workspace", pid, path), name, agent="analyst")
    assert r["status"] == "rejected" and any(why in x for x in r["reasons"]), (name, r)
assert "0 (flat) or 1" in lab.submit(store.path("workspace", pid, short), "short")["error"]
assert "too many" in lab.submit(store.path("workspace", pid, grid), "grid")["error"]

b = lab.board()
assert set(b) >= {"trend", "cheat", "zscore"} and b["cheat"]["status"] == "rejected"
assert len(lab.trials()) == 5
assert open(store.path("lab", "strategies", "trend.py")).read() == open(store.path("workspace", pid, good)).read(), "frozen copy"
# الايجنت ما بيقدروا يكتبوا على نتائج المختبر
try:
    tools.write_file(ctx, {"path": "../../lab/board.json", "content": "{}"}); raise SystemExit("board writable!")
except PermissionError:
    pass
assert "lab_submit" in c.st["agents"]["analyst"]["tools"] and "lab_submit" not in c.st["agents"]["writer"]["tools"]
# نفس الاسم مرة ثانية -> نسخة جديدة، مش كتابة فوق القديمة
r2 = lab.submit(store.path("workspace", pid, good), "trend")
assert r2["name"] == "trend_v2"
# الحد اليومي
lab.MAX_PER_DAY = len(lab.trials())
assert "limit" in lab.submit(store.path("workspace", pid, good), "again")["error"]
lab.MAX_PER_DAY = 12

# اختبار المستقبل: أيام جديدة بعد التجميد
fz = pd.read_csv(os.path.join(data_dir, "gold_GCF_daily.csv"), parse_dates=["date"]).set_index("date")["close"]
fw = pd.Series(fz.iloc[-1] * np.exp(np.cumsum(np.full(10, 0.01))), index=pd.bdate_range(fz.index[-1] + pd.Timedelta(days=1), periods=10))
fw.rename("close").rename_axis("date").to_csv(os.path.join(data_dir, "gold_GCF_forward.csv"))
import gold_toolkit.data as gd
gd.update_forward = lambda days=90: 10                         # بدون شبكة بالاختبار
b = lab.board()
fwd = [k for k, v in b.items() if v["status"] == "forward"]
if fwd:
    lab.daily()
    f = lab.board()[fwd[0]]["forward"]
    assert f["days"] == 10 and abs(f["buy_hold"] - (np.exp(0.01) ** 10 - 1)) < 1e-3, f
    assert os.path.exists(store.path("lab", "forward", fwd[0] + ".json"))
    print("  (forward test checked on", fwd[0], ")")
s = lab.summary()
assert "Total trials so far: 6" in s and "cheat" in s

# صفحة المدينة فيها المختبر
from city import cityview
h = cityview.render()
assert "مختبر الاستراتيجيات" in h and '"name": "trend"' in h

# حفظ واسترجاع ذاكرة المدينة
from city import persist
persist.DST = tempfile.mkdtemp()
persist.export_state()
assert os.path.exists(os.path.join(persist.DST, "lab", "board.json")) and os.path.exists(os.path.join(persist.DST, "state.json"))
old_home = os.environ["CITY_HOME"]; os.environ["CITY_HOME"] = tempfile.mkdtemp(); store.init()
assert "imported" in persist.import_state() and "trend" in lab.board()
print("ALL LAB TESTS PASSED")
