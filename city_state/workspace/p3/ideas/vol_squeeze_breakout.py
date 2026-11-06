import numpy as np
import pandas as pd
HYPOTHESIS = ("Volatility compression precedes expansion; upside breakouts that start from a low-volatility squeeze "
              "carry on as crowded positioning unwinds.")
PARAMS = {"q": [0.2, 0.35, 0.5], "N": [20, 40], "X": [10, 20]}

def signal(close, q, N, X):
    vol = close.pct_change().rolling(20).std()
    squeeze = (vol <= vol.rolling(250).quantile(q)).shift(1, fill_value=False).values
    hi = close.shift(1).rolling(N).max().values
    lo = close.shift(1).rolling(X).min().values
    c = close.values
    pos, cur = np.zeros(len(c)), 0.0
    for i in range(len(c)):
        if np.isnan(hi[i]) or np.isnan(lo[i]):
            continue
        if cur == 0 and squeeze[i] and c[i] > hi[i]:
            cur = 1.0
        elif cur == 1 and c[i] < lo[i]:
            cur = 0.0
        pos[i] = cur
    return pd.Series(pos, index=close.index)
