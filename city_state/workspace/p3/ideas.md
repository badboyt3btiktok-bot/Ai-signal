# Research Day #1 — hypotheses

Context: the old catalog (SMA cross, RSI reversion, breakout) failed to beat buy & hold. Lab board is empty (0 trials).
Planned seasonality idea dropped before submitting: a calendar rule trades ~1x/year, so it cannot reach
risk.MIN_TRADES=10 on ~7 train years; submitting it would waste a trial.

## 1. vol_filtered_momentum (time-series momentum, risk-regime filter)
- Mechanism: gold moves on slow macro flows (real rates, central-bank and ETF accumulation) that persist for months;
  time-series momentum is documented across commodities. Momentum crashes cluster in high-volatility regimes, so skip them.
- Rule: long if close/close[L] - 1 > 0 AND 20-day realized vol <= its own trailing 250-day q-quantile (q=1.0 = no filter).
- Grid: L in {60,120,250} x q in {0.6, 0.8, 1.0} = 9 combos.
- Falsified if: validation Sharpe <= buy & hold, or forward test lags buy & hold after ~60 days.

## 2. dip_in_uptrend (mean reversion only inside a long-term uptrend)
- Mechanism: in a secular uptrend, short pullbacks come from liquidity events (stop runs, ETF outflows, margin calls)
  rather than new information, and long-horizon buyers step in. Outside the uptrend, dips are not bought.
- Rule: uptrend = close > SMA(T). Enter when uptrend and close is >= x below its trailing 20-day high.
  Exit when close > SMA(E) (rebound) or uptrend ends.
- Grid: T in {100,200} x x in {0.03,0.05,0.07} x E in {10,20} = 12 combos.
- Falsified if: fewer than the minimum trades, or no improvement over buy & hold on validation/forward.

## 3. vol_squeeze_breakout (volatility compression -> expansion)
- Mechanism: volatility clusters and mean-reverts; low-volatility compressions build positioning that unwinds in a
  directional move. Only take upside breakouts that start from a squeeze.
- Rule: squeeze = 20-day vol in the bottom q of its trailing 250-day distribution (checked on the previous day).
  Enter when squeeze and close > highest close of the prior N days. Exit when close < lowest close of the prior X days.
- Grid: q in {0.2,0.35,0.5} x N in {20,40} x X in {10,20} = 12 combos.
- Falsified if: rejected by the lab, or forward test lags buy & hold.

Total planned trials today: 3 (one submission per idea).
