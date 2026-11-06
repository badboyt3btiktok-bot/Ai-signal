description: Ready Python toolkit for backtesting gold (XAUUSD) strategies with train/val/test split. Import from gold_toolkit.
# gold_toolkit
Available via PYTHONPATH in run_python: `from gold_toolkit import strategies, backtest, risk, data`
- data.from_yahoo() -> REAL gold futures (GC=F) daily closes, cached in shared/data/gold_GCF_daily.csv (frozen; use this)
- data.from_csv(path) for a CSV; data.demo() is SYNTHETIC test data only, never report results on it
- strategies.CATALOG (sma_cross, rsi_reversion, breakout), strategies.signal(template, params, close) -> position series
- backtest.evaluate(close, pos, i, j) -> dict(return, sharpe, max_dd, trades, buy_hold)
- risk.check / risk.final_check -> hard guardrails (min trades, max drawdown, overfitting gap)
RULES: tune on train, select on validation, open the final test ONCE. Extend the toolkit with new strategy templates if needed.
