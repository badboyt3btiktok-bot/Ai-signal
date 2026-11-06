import json
import numpy as np, pandas as pd
from gold_toolkit import data, strategies
w = json.load(open("winner.json")); p = w["params"]; c = data.from_yahoo()
pine = strategies.pine_fallback(w)
hdr = ("// Agent City - Gold " + w["name"] + " | SIGNALS ONLY, no order execution. Not financial advice.\n"
       "// Honest result: see REPORT_GOLD.md (failed the final test vs buy & hold).\n")
open("indicator.pine", "w").write(hdr + pine)

def pine_sim(r, low, high):
    inpos, out = False, []
    for x in r:
        buy = (not inpos) and x < low      # NaN comparisons are False, as in Pine
        sell = inpos and x > high
        if buy: inpos = True
        if sell: inpos = False
        out.append(1.0 if inpos else 0.0)
    return np.array(out)

def pine_rsi(close, n):                    # TradingView ta.rsi: RMA seeded with SMA of first n changes
    d = close.diff()
    up, dn = d.clip(lower=0).values, (-d.clip(upper=0)).values
    au, ad = np.full(len(d), np.nan), np.full(len(d), np.nan)
    au[n], ad[n] = up[1:n+1].mean(), dn[1:n+1].mean()
    for i in range(n + 1, len(d)):
        au[i] = (au[i-1] * (n - 1) + up[i]) / n
        ad[i] = (ad[i-1] * (n - 1) + dn[i]) / n
    return 100 - 100 / (1 + au / ad)

ref = strategies.signal(w["template"], p, c).values
same_rsi = pine_sim(strategies._rsi(c, p["period"]).values, p["low"], p["high"])
tv_rsi = pine_sim(pine_rsi(c, p["period"]), p["low"], p["high"])
m1, m2 = int((same_rsi != ref).sum()), int((tv_rsi != ref).sum())
txt = (f"bars={len(c)}\nstate-machine parity (toolkit RSI): mismatched bars = {m1}\n"
       f"with TradingView-style RSI (SMA-seeded RMA): mismatched bars = {m2} ({m2/len(c):.2%})\n")
if m2:
    idx = np.where(tv_rsi != ref)[0]
    txt += f"first/last mismatch: {c.index[idx[0]].date()} / {c.index[idx[-1]].date()}\n"
open("parity.txt", "w").write(txt); print(txt); print(open("indicator.pine").read())
