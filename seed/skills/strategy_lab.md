description: How to research trading strategies in the city's Strategy Lab (write a module, lab_submit, read lab_board). Read before any strategy research.
# strategy_lab
The Strategy Lab is how the city searches for edges honestly. YOU write ideas; THE CITY evaluates them.

## Strategy module (one file per idea, in your workspace)
```python
HYPOTHESIS = "Why this could work, in economic terms (who is on the other side, what behaviour repeats)."
PARAMS = {"lookback": [60, 120, 250]}          # small grid, <= 60 combinations
def signal(close, lookback):                   # close: pd.Series of daily GC=F closes (DatetimeIndex)
    return (close / close.shift(lookback) - 1 > 0).astype(float)   # 0 = flat, 1 = long, CAUSAL ONLY
```
- Only use data up to each day (rolling/shift(+k)). Never shift(-k), never full-sample stats (mean/std of the whole series).
  The lab re-runs your signal on truncated data; any difference = look-ahead = rejected.
- Long/flat only (0/1). The backtest charges a cost per position change; daily flipping is punished.

## Submit
`lab_submit(path="ideas/tsmom.py", name="tsmom", hypothesis="...")` returns the verdict:
- The lab picks params on TRAIN only, looks at VALIDATION once, applies risk.py
  (min trades on train/val, max drawdown, overfit gap, must beat buy & hold Sharpe on validation).
- `promoted` => the idea enters the LIVE FORWARD TEST on days nobody has seen. That is the real judge.
- Each submission counts. Daily limit exists. Do NOT resubmit tweaks of a rejected idea to chase validation:
  with many trials some will pass by luck. Prefer genuinely different hypotheses.

## Learn
`lab_board()` shows forward results, total trials, and recent rejections with reasons. Read it first, every time.
Good families to consider (check the board first): trend/time-series momentum, volatility regimes/filters,
mean reversion only in calm regimes, seasonality (month/day effects), breakout with volatility confirmation,
combinations of two weak signals. Bad: anything that needs future data, huge grids, curve-fitting to validation.

## Report honestly
If nothing passes or forward results lag buy & hold, say so. "No edge found" is a valid, useful result.
