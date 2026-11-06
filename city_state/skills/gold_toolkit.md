description: Ready Python toolkit for backtesting gold (XAUUSD) strategies with train/val/test split. Import from gold_toolkit.
# gold_toolkit
Available via PYTHONPATH in run_python: `from gold_toolkit import strategies, backtest, risk, data`
- data.from_yahoo() -> REAL gold futures (GC=F) daily closes, cached in shared/data/gold_GCF_daily.csv (frozen; use this)
- data.from_csv(path) for a CSV; data.demo() is SYNTHETIC test data only, never report results on it
- strategies.CATALOG (sma_cross, rsi_reversion, breakout), strategies.signal(template, params, close) -> position series
- backtest.evaluate(close, pos, i, j) -> dict(return, sharpe, max_dd, trades, buy_hold, bh_sharpe, bh_max_dd)
- protocol.Protocol(close): .evaluate(pos) train+val, .check(pos) risk.check, .open_final(name, params, pos) ONCE (writes final_test.lock; refuses failed strategies). USE THIS, never slice the test period yourself.
- risk.check / risk.final_check -> hard guardrails (min trades on train/val/test, max drawdown, overfitting gap, must beat buy & hold Sharpe)
- strategies.pine_fallback(c) -> Pine Script that mirrors signal() exactly (stateful)
RULES: tune on train, select on validation, open the final test ONCE via protocol.open_final. Agent code runs in an OFFLINE sandbox; shared/ is read-only. If no strategy passes, say so honestly. Extend the toolkit with new strategy templates if needed.
