"""Python re-implementation of GoldDipInUptrend.mq5's OnCalculate loop (line by line), compared with the lab module."""
import importlib.util, numpy as np
from gold_toolkit import data
T, X, E = 100, 0.03, 20
c = data.from_yahoo().values
pos = np.zeros(len(c))
for i in range(len(c)):
    prev = pos[i - 1] if i > 0 else 0.0
    cur = prev
    if i >= 19 and i >= E - 1:
        trend = i >= T - 1 and c[i] > c[i - T + 1:i + 1].mean()
        hi20 = c[i - 19:i + 1].max()
        exit_ma = c[i - E + 1:i + 1].mean()
        if prev == 0 and trend and c[i] <= hi20 * (1 - X):
            cur = 1.0
        elif prev == 1 and ((c[i] > exit_ma and c[i] > c[i - 1]) or not trend):
            cur = 0.0
    pos[i] = cur
spec = importlib.util.spec_from_file_location("m", "../p3/ideas/dip_in_uptrend.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
ref = m.signal(data.from_yahoo(), T=T, x=X, E=E).values
bad = np.where(pos != ref)[0]
print("bars:", len(c), "| mismatches:", len(bad), "| entries:", int((np.diff(pos) > 0).sum()), "| exits:", int((np.diff(pos) < 0).sum()))
if len(bad): print("first mismatch index:", bad[:5])
