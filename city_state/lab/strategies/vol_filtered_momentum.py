import numpy as np
HYPOTHESIS = ("Time-series momentum: gold moves on slow macro flows that persist for months; skip high-volatility "
              "regimes where momentum crashes cluster.")
PARAMS = {"L": [60, 120, 250], "q": [0.6, 0.8, 1.0]}

def signal(close, L, q):
    mom = close / close.shift(L) - 1 > 0
    vol = close.pct_change().rolling(20).std() * np.sqrt(252)
    calm = vol <= vol.rolling(250).quantile(q) if q < 1 else vol.notna()
    return (mom & calm).astype(float)
