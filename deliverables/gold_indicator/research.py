"""بروتوكول بحث مؤشر الذهب (مثبّت قبل رؤية أي نتيجة):
1) البيانات: GC=F يومي مجمّد (shared/data/gold_GCF_daily.csv). تقسيم زمني 60% train / 20% val / 20% test.
2) Stage 1 (train فقط): grid كامل على قوالب CATALOG. فلتر: صفقات train >= MIN_TRADES و |DD| <= MAX_DD.
   أفضل 5 لكل قالب حسب Sharpe على train.
3) Stage 2 (val فقط): risk.check (بدون أي تعديل) لكل مرشح. الفائز = أعلى Sharpe على val بين الناجحين.
   إذا ما في ناجح: بنوقف وما بنفتح الاختبار النهائي.
4) Stage 3: final test بينفتح مرة وحدة للفائز فقط (ملف قفل final_test.lock)، ثم risk.final_check.
المؤشرات كلها سببية؛ المركز بيتطبق على عائد اليوم التالي (pos.shift(1)) مع تكلفة COST لكل تغيير مركز.
"""
import itertools, json, os, sys
import pandas as pd
from gold_toolkit import backtest, data, risk, strategies

LOCK = "final_test.lock"
GRID = {
    "sma_cross": {"fast": range(5, 51, 5), "slow": range(20, 251, 10)},
    "rsi_reversion": {"period": range(5, 31, 5), "low": range(15, 41, 5), "high": range(55, 86, 5)},
    "breakout": {"entry": range(10, 121, 10), "exit": range(5, 61, 5)},
}

close = data.from_yahoo()
n = len(close)
a, b = int(n * 0.6), int(n * 0.8)
seg = {"train": (0, a), "val": (a, b), "test": (b, n)}
ones = pd.Series(1.0, index=close.index)
info = {"data": {"rows": n, "start": str(close.index[0].date()), "end": str(close.index[-1].date())},
        "segments": {k: [str(close.index[i].date()), str(close.index[j - 1].date())] for k, (i, j) in seg.items()},
        "buy_hold": {k: backtest.evaluate(close, ones, i, j) for k, (i, j) in seg.items() if k != "test"}}

# ---- Stage 1: train ----
cands, tried = [], 0
for t, g in GRID.items():
    rows = []
    for vals in itertools.product(*g.values()):
        c = strategies.sanitize({"template": t, "params": dict(zip(g, vals))})
        if not c:
            continue
        tried += 1
        pos = strategies.signal(t, c["params"], close)
        tr = backtest.evaluate(close, pos, *seg["train"])
        if tr["trades"] >= risk.MIN_TRADES and abs(tr["max_dd"]) <= risk.MAX_DD:
            rows.append((tr["sharpe"], c, pos, tr))
    rows.sort(key=lambda r: -r[0])
    cands += rows[:5]
info["candidates_tried"] = tried

# ---- Stage 2: validation + risk.check ----
results = []
for _, c, pos, tr in cands:
    va = backtest.evaluate(close, pos, *seg["val"])
    chk = risk.check({"train": tr, "val": va})
    results.append({"template": c["template"], "params": c["params"], "train": tr, "val": va, "risk": chk})
info["stage2"] = results
passed = [r for r in results if r["risk"]["passed"]]
print(f"tried={tried} shortlisted={len(results)} passed_risk={len(passed)}")
for r in results:
    print(f"{r['template']:<14}{str(r['params']):<38} train S={r['train']['sharpe']:>5} "
          f"val S={r['val']['sharpe']:>5} DD={r['val']['max_dd']:>7} tr={r['val']['trades']:>3} "
          f"{'PASS' if r['risk']['passed'] else 'FAIL ' + '; '.join(r['risk']['reasons'])}")
print("buy&hold:", info["buy_hold"])

if not passed:
    info["decision"] = "no strategy passed risk.check on validation; final test NOT opened"
    json.dump(info, open("results.json", "w"), ensure_ascii=False, indent=1)
    sys.exit(print(info["decision"]))

win = max(passed, key=lambda r: r["val"]["sharpe"])
info["winner"] = win
print("WINNER:", win["template"], win["params"])

# ---- Stage 3: final test (once) ----
if "--open-final" not in sys.argv:
    json.dump(info, open("results.json", "w"), ensure_ascii=False, indent=1)
    sys.exit(print("final test still sealed. re-run with --open-final to open it ONCE."))
if os.path.exists(LOCK):
    sys.exit("final test was already opened once: " + open(LOCK).read())
pos = strategies.signal(win["template"], win["params"], close)
te = backtest.evaluate(close, pos, *seg["test"])
fc = risk.final_check(te)
info["final_test"] = {"metrics": te, "final_check": fc, "buy_hold": backtest.evaluate(close, ones, *seg["test"])}
open(LOCK, "w").write(json.dumps({"strategy": win["template"], "params": win["params"], "test": te, "check": fc}))
json.dump(info, open("results.json", "w"), ensure_ascii=False, indent=1)
print("FINAL TEST:", te, "\nfinal_check:", fc, "\nbuy&hold test:", info["final_test"]["buy_hold"])
