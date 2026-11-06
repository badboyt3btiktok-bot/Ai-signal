"""قوالب الاستراتيجيات. الـ LLM بيختار قالب + باراميترات، والكود هو اللي بيحسب الإشارات (مش الـ LLM)."""
import random
import numpy as np
import pandas as pd

CATALOG = {
    "sma_cross":     {"fast": [5, 50],  "slow": [20, 250]},
    "rsi_reversion": {"period": [5, 30], "low": [15, 40], "high": [55, 85]},
    "breakout":      {"entry": [10, 120], "exit": [5, 60]},
}


def sanitize(c: dict):
    """بيتأكد إن المرشح صالح وبيقصّ الباراميترات ضمن الحدود."""
    try:
        t = c["template"]
        spec = CATALOG[t]
        p = {k: int(min(max(c["params"][k], lo), hi)) for k, (lo, hi) in spec.items()}
        if t == "sma_cross" and p["fast"] >= p["slow"]:
            return None
        if t == "rsi_reversion" and p["low"] >= p["high"]:
            return None
        return {"name": c.get("name", t), "template": t, "params": p,
                "rationale": c.get("rationale", "")}
    except Exception:
        return None


def random_candidates(n=5):
    out = []
    while len(out) < n:
        t = random.choice(list(CATALOG))
        p = {k: random.randint(lo, hi) for k, (lo, hi) in CATALOG[t].items()}
        c = sanitize({"template": t, "params": p, "name": f"{t}_{len(out)}"})
        if c:
            out.append(c)
    return out


def _rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def signal(template: str, p: dict, close: pd.Series) -> pd.Series:
    """بترجع مركز (0 أو 1) لكل يوم. كل المؤشرات سببية (بدون نظر للمستقبل)."""
    pos = np.zeros(len(close))
    c = close.values
    if template == "sma_cross":
        f = close.rolling(p["fast"]).mean().values
        s = close.rolling(p["slow"]).mean().values
        pos = np.where(f > s, 1.0, 0.0)
    elif template == "rsi_reversion":
        r = _rsi(close, p["period"]).values
        cur = 0.0
        for i in range(len(c)):
            if np.isnan(r[i]):
                pos[i] = 0
                continue
            if cur == 0 and r[i] < p["low"]:
                cur = 1.0
            elif cur == 1 and r[i] > p["high"]:
                cur = 0.0
            pos[i] = cur
    elif template == "breakout":
        hi = close.shift(1).rolling(p["entry"]).max().values
        lo = close.shift(1).rolling(p["exit"]).min().values
        cur = 0.0
        for i in range(len(c)):
            if np.isnan(hi[i]) or np.isnan(lo[i]):
                pos[i] = 0
                continue
            if cur == 0 and c[i] > hi[i]:
                cur = 1.0
            elif cur == 1 and c[i] < lo[i]:
                cur = 0.0
            pos[i] = cur
    return pd.Series(pos, index=close.index)


PINE = {
    "sma_cross": """//@version=5
indicator("Gold City - SMA Cross", overlay=true)
fast = ta.sma(close, {fast})
slow = ta.sma(close, {slow})
plot(fast, color=color.orange)
plot(slow, color=color.blue)
plotshape(ta.crossover(fast, slow), "BUY", shape.triangleup, location.belowbar, color.green, size=size.small)
plotshape(ta.crossunder(fast, slow), "SELL", shape.triangledown, location.abovebar, color.red, size=size.small)
alertcondition(ta.crossover(fast, slow), "BUY", "Gold BUY signal")
alertcondition(ta.crossunder(fast, slow), "SELL", "Gold SELL signal")
""",
    "rsi_reversion": """//@version=5
indicator("Gold City - RSI Reversion", overlay=true)
r = ta.rsi(close, {period})
buy = ta.crossunder(r, {low})
sell = ta.crossover(r, {high})
plotshape(buy, "BUY", shape.triangleup, location.belowbar, color.green, size=size.small)
plotshape(sell, "SELL", shape.triangledown, location.abovebar, color.red, size=size.small)
alertcondition(buy, "BUY", "Gold BUY signal")
alertcondition(sell, "SELL", "Gold SELL signal")
""",
    "breakout": """//@version=5
indicator("Gold City - Breakout", overlay=true)
hi = ta.highest(close, {entry})[1]
lo = ta.lowest(close, {exit})[1]
buy = close > hi
sell = close < lo
plot(hi, color=color.green)
plot(lo, color=color.red)
plotshape(buy and not buy[1], "BUY", shape.triangleup, location.belowbar, color.green, size=size.small)
plotshape(sell and not sell[1], "SELL", shape.triangledown, location.abovebar, color.red, size=size.small)
alertcondition(buy and not buy[1], "BUY", "Gold BUY signal")
alertcondition(sell and not sell[1], "SELL", "Gold SELL signal")
""",
}


def pine_fallback(c: dict) -> str:
    return PINE[c["template"]].format(**c["params"])
