import os
import numpy as np
import pandas as pd


def demo(n=2500, seed=7) -> pd.Series:
    """بيانات تجريبية اصطناعية (مش بيانات ذهب حقيقية) لتجربة النظام."""
    rng = np.random.default_rng(seed)
    drift = np.repeat(rng.normal(0.0003, 0.0006, n // 250 + 1), 250)[:n]
    r = drift + rng.normal(0, 0.009, n)
    idx = pd.bdate_range(end="2026-11-06", periods=n)
    return pd.Series(1200 * np.exp(np.cumsum(r)), index=idx, name="close")


def from_csv(path: str) -> pd.Series:
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    date = "date" if "date" in df else df.columns[0]
    close = "close" if "close" in df else "adj close"
    s = pd.Series(df[close].values, index=pd.to_datetime(df[date]), name="close")
    return s.sort_index().dropna()


CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "gold_GCF_daily.csv")


def from_yahoo(years=12, cache=CACHE, refresh=False) -> pd.Series:
    """إغلاقات يومية لعقود الذهب الآجلة GC=F (مش سبوت XAUUSD بالظبط، بس قريبة جداً).
    أول مرة بتنزّل وبتحفظ CSV، وبعدها كل الفريق بيقرأ نفس النسخة المجمّدة
    (عشان train/val/test ما يتغيروا بين تشغيل وتشغيل). الشمعة اليومية غير المكتملة بتنحذف."""
    if cache and os.path.exists(cache) and not refresh:
        return from_csv(cache)
    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError("No cached gold data and no yfinance here (agent code runs in an offline sandbox). "
                           "The owner must run: python agentcity.py data")
    df = yf.download("GC=F", period=f"{years}y", interval="1d", progress=False, auto_adjust=True)
    c = df["Close"]
    c = c.iloc[:, 0] if hasattr(c, "columns") else c
    c = c.dropna().rename("close")
    c.index = pd.to_datetime(c.index).tz_localize(None)
    if len(c) and c.index[-1].date() >= pd.Timestamp.utcnow().date():
        c = c.iloc[:-1]
    if len(c) < 500:
        raise RuntimeError(f"yfinance returned only {len(c)} rows")
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        c.rename_axis("date").to_csv(cache)
    return c
