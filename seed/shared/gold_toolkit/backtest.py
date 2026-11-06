import numpy as np
import pandas as pd

COST = 0.0002  # تكلفة تقريبية (سبريد+عمولة) لكل تغيير مركز


def evaluate(close: pd.Series, pos: pd.Series, i: int, j: int) -> dict:
    ret = close.pct_change().fillna(0)
    changes = pos.diff().abs().fillna(0)
    strat = pos.shift(1).fillna(0) * ret - COST * changes
    s = strat.iloc[i:j]
    sd = s.std()
    sharpe = float(s.mean() / sd * np.sqrt(252)) if sd and sd > 0 else 0.0
    eq = (1 + s).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    trades = int(changes.iloc[i:j].sum() // 2)
    bh = float(close.iloc[j - 1] / close.iloc[i] - 1)
    b_ = ret.iloc[i:j]                        # المقارنة: شراء واحتفاظ بنفس الفترة (benchmark)
    bsd = b_.std()
    bh_sharpe = float(b_.mean() / bsd * np.sqrt(252)) if bsd and bsd > 0 else 0.0
    beq = (1 + b_).cumprod()
    return {"return": round(float(eq.iloc[-1] - 1), 4), "sharpe": round(sharpe, 2),
            "max_dd": round(dd, 4), "trades": trades, "buy_hold": round(bh, 4),
            "bh_sharpe": round(bh_sharpe, 2), "bh_max_dd": round(float((beq / beq.cummax() - 1).min()), 4)}
