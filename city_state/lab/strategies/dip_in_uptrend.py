import numpy as np
import pandas as pd
HYPOTHESIS = ("Buy liquidity-driven pullbacks only inside a long-term uptrend; long-horizon buyers absorb dips in a "
              "secular bull, while dips outside the uptrend are not bought.")
PARAMS = {"T": [100, 200], "x": [0.03, 0.05, 0.07], "E": [10, 20]}

def signal(close, T, x, E):
    c = close.values
    trend = (close > close.rolling(T).mean()).values
    high20 = close.rolling(20).max().values
    exit_ma = close.rolling(E).mean().values
    pos, cur = np.zeros(len(c)), 0.0
    for i in range(len(c)):
        if np.isnan(high20[i]) or np.isnan(exit_ma[i]):
            continue
        if cur == 0 and trend[i] and c[i] <= high20[i] * (1 - x):
            cur = 1.0
        elif cur == 1 and (c[i] > exit_ma[i] and c[i] > c[i - 1] or not trend[i]):
            cur = 0.0
        pos[i] = cur
    return pd.Series(pos, index=close.index)
