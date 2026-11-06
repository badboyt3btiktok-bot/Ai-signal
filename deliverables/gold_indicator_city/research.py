"""Pre-registered protocol (train/val only; the test segment is never evaluated here).
Grid over strategies.CATALOG; stage 1 = train filter + top 5/template by train Sharpe;
stage 2 = protocol.check (risk.check incl. buy&hold benchmark); winner = best val Sharpe among passers."""
import itertools, json
import pandas as pd
from gold_toolkit import data, protocol, strategies, risk

close = data.from_yahoo()
r = close.pct_change().dropna()
dq = {"rows": len(close), "start": str(close.index[0].date()), "end": str(close.index[-1].date()),
      "nan": int(close.isna().sum()), "non_positive": int((close <= 0).sum()),
      "largest_moves": {str(k.date()): round(float(v), 4) for k, v in r.abs().nlargest(3).items()}}
pr = protocol.Protocol(close, lock_dir="__never__")
GRID = {"sma_cross": {"fast": range(5, 51, 5), "slow": range(20, 251, 10)},
        "rsi_reversion": {"period": range(5, 31, 5), "low": range(15, 41, 5), "high": range(55, 86, 5)},
        "breakout": {"entry": range(10, 121, 10), "exit": range(5, 61, 5)}}
short, tried = [], 0
for t, g in GRID.items():
    rows = []
    for vals in itertools.product(*g.values()):
        c = strategies.sanitize({"template": t, "params": dict(zip(g, vals))})
        if not c:
            continue
        tried += 1
        pos = strategies.signal(t, c["params"], close)
        tr = pr.evaluate(pos)["train"]
        if tr["trades"] >= risk.MIN_TRADES and abs(tr["max_dd"]) <= risk.MAX_DD:
            rows.append((tr["sharpe"], c, pos))
    rows.sort(key=lambda x: -x[0])
    short += rows[:5]
cands = []
for _, c, pos in short:
    m = pr.evaluate(pos)
    chk = pr.check(pos)
    cands.append({"name": f"{c['template']}_" + "_".join(map(str, c["params"].values())), "template": c["template"],
                  "params": c["params"], "train": m["train"], "val": m["val"], "risk": chk})
passed = [c for c in cands if c["risk"]["passed"]]
win = max(passed, key=lambda c: c["val"]["sharpe"]) if passed else None
json.dump({"data_quality": dq, "segments": pr.dates(), "tried": tried, "candidates": cands}, open("candidates.json", "w"),
          ensure_ascii=False, indent=1)
json.dump(win or "none", open("winner.json", "w"), ensure_ascii=False, indent=1)
print("data:", dq)
print("segments:", pr.dates())
print(f"tried={tried} shortlisted={len(cands)} passed={len(passed)}")
for c in cands:
    print(f"{c['name']:<26} trS={c['train']['sharpe']:>5} vaS={c['val']['sharpe']:>5} (bh {c['val']['bh_sharpe']}) "
          f"vaTr={c['val']['trades']:>2} {'PASS' if c['risk']['passed'] else 'FAIL'}")
print("WINNER:", win and (win["name"], win["val"]))
