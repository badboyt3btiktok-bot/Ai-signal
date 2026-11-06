"""مقيّم مختبر الاستراتيجيات (كود ثابت للمدينة، بيشتغل جوا Docker). الايجنت ما بيشغّلوه بإيدهم؛ المدينة بتشغّله.

ملف الاستراتيجية لازم يعرّف:
    HYPOTHESIS = "ليش ممكن تشتغل"          (نص)
    PARAMS = {"lookback": [20, 60, 120]}      (شبكة صغيرة: أقصى 60 تركيبة)
    def signal(close: pd.Series, **params) -> pd.Series   # مركز 0 (برّا) أو 1 (شاري) لكل يوم، سببي

python lab_harness.py evaluate strat.py
python lab_harness.py forward  strat.py '{"lookback": 60}'
"""
import importlib.util, itertools, json, math, sys
import numpy as np
import pandas as pd
from gold_toolkit import backtest, data, protocol, risk

MAX_COMBOS = 60


def load(path):
    spec = importlib.util.spec_from_file_location("strategy", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    if not callable(getattr(m, "signal", None)):
        raise ValueError("strategy must define signal(close, **params)")
    grid = getattr(m, "PARAMS", {}) or {}
    if not isinstance(grid, dict) or not all(isinstance(v, (list, tuple)) and v for v in grid.values()):
        raise ValueError("PARAMS must be a dict of non-empty lists")
    combos = [dict(zip(grid, vals)) for vals in itertools.product(*grid.values())] or [{}]
    if len(combos) > MAX_COMBOS:
        raise ValueError(f"too many parameter combinations ({len(combos)} > {MAX_COMBOS}); shrink the grid")
    return m, combos


def positions(m, close, p):
    pos = m.signal(close.copy(), **p)
    pos = pd.Series(np.asarray(pos, dtype=float), index=close.index) if not isinstance(pos, pd.Series) else pos.astype(float)
    if len(pos) != len(close):
        raise ValueError("signal() must return one value per day")
    pos = pos.reindex(close.index).fillna(0.0)
    if not set(np.unique(pos.values)) <= {0.0, 1.0}:
        raise ValueError("positions must be 0 (flat) or 1 (long)")
    return pos


def causal(m, close, p, full_pos):
    """نفس الاستراتيجية على بيانات مقطوعة لازم تعطي نفس الإشارات للأيام اللي قبل القطع (ما في نظر للمستقبل)."""
    n = len(close)
    for frac in (0.45, 0.62, 0.81, 0.93):
        k = int(n * frac)
        cut = positions(m, close.iloc[:k], p).values
        if not np.array_equal(cut, full_pos.values[:k]):
            bad = int(np.argmax(cut != full_pos.values[:k]))
            return False, f"look-ahead: signal at {close.index[bad].date()} changes when future data is removed"
    return True, ""


def evaluate(path):
    m, combos = load(path)
    close = data.from_yahoo()
    pr = protocol.Protocol(close, lock_dir="/nonexistent")
    rows = []
    for p in combos:
        pos = positions(m, close, p)
        tr = backtest.evaluate(close, pos, *pr.seg["train"])
        rows.append({"params": p, "train": tr, "ok": tr["trades"] >= risk.MIN_TRADES and abs(tr["max_dd"]) <= risk.MAX_DD})
    ok = [r for r in rows if r["ok"]]
    out = {"combos": len(combos), "train_ok": len(ok), "hypothesis": str(getattr(m, "HYPOTHESIS", ""))[:500]}
    top = max(ok or rows, key=lambda r: r["train"]["sharpe"])   # فحص الغش أول شي، حتى لو كانت رح تنرفض لسبب ثاني
    good, why = causal(m, close, top["params"], positions(m, close, top["params"]))
    if not good:
        out.update(verdict="rejected", reasons=[why], params=top["params"], train=top["train"])
        return out
    if not ok:
        out.update(verdict="rejected", reasons=["no parameter set passed the train filter (min trades / max drawdown)"],
                   best_train=max(rows, key=lambda r: r["train"]["sharpe"]))
        return out
    best = top                                                  # الاختيار على التدريب فقط
    pos = positions(m, close, best["params"])
    val = backtest.evaluate(close, pos, *pr.seg["val"])        # نظرة وحدة على التحقق
    chk = risk.check({"train": best["train"], "val": val})
    # معلومة إحصائية: كم بيعني Sharpe التحقق بعد كل هالمحاولات؟ (SE تقريبي = 1/sqrt(سنوات))
    yrs = (pr.seg["val"][1] - pr.seg["val"][0]) / 252
    out.update(params=best["params"], train=best["train"], val=val, risk=chk, val_years=round(yrs, 2),
               val_sharpe_se=round(1 / math.sqrt(yrs), 2), verdict="promoted" if chk["passed"] else "rejected",
               reasons=chk["reasons"])
    return out


def forward(path, params, since=None):
    m, _ = load(path)
    s = data.full()
    end = data.freeze_end()
    pos = positions(m, s, params)
    ret = s.pct_change().fillna(0)
    strat = pos.shift(1).fillna(0) * ret - backtest.COST * pos.diff().abs().fillna(0)
    start = pd.Timestamp(since) if since else end
    mask = s.index > start
    days = [{"d": str(d.date()), "close": round(float(s[d]), 2), "pos": int(pos[d]),
             "ret": round(float(strat[d]), 6), "bh": round(float(ret[d]), 6)} for d in s.index[mask]]
    eq = float(np.prod([1 + x["ret"] for x in days])) if days else 1.0
    bh = float(np.prod([1 + x["bh"] for x in days])) if days else 1.0
    return {"since": str(start.date()), "days": len(days), "position_now": int(pos.iloc[-1]),
            "last_date": str(s.index[-1].date()), "return": round(eq - 1, 4), "buy_hold": round(bh - 1, 4),
            "trades": int(pos[mask].diff().abs().fillna(0).sum() // 2), "series": days[-400:]}


if __name__ == "__main__":
    try:
        if sys.argv[1] == "evaluate":
            res = evaluate(sys.argv[2])
        else:
            res = forward(sys.argv[2], json.loads(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else None)
        print("LAB_RESULT " + json.dumps(res, ensure_ascii=False, default=str))
    except Exception as e:
        print("LAB_RESULT " + json.dumps({"verdict": "error", "error": f"{type(e).__name__}: {e}"[:800]}))
