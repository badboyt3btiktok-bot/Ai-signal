"""ايجنت المخاطر (قواعد صارمة بالكود، مش رأي LLM). أي استراتيجية بتفشل هون بتنرفض.
ملاحظة: القواعد بتتشدد بس، ما بتتخفف. أي مقياس ناقص = رفض (fail closed)."""
MIN_TRADES = 10          # صفقات على train
MIN_VAL_TRADES = 5       # صفقات على validation (أقل من هيك = Sharpe ضجيج)
MIN_TEST_TRADES = 3      # صفقات على الاختبار النهائي
MAX_DD = 0.30
MIN_VAL_SHARPE = 0.3

# تنبيه: ما في أي كود تنفيذ صفقات حقيقية بهالمشروع. الإشارات فقط.
LIVE_TRADING = False


def _beats_benchmark(m, label, reasons):
    if "bh_sharpe" not in m:
        reasons.append(f"مقارنة الشراء والاحتفاظ ناقصة على {label} (استعمل backtest.evaluate الحالي)")
    elif m["sharpe"] < m["bh_sharpe"]:
        reasons.append(f"ما بتتفوق على الشراء والاحتفاظ على {label} (Sharpe {m['sharpe']} < {m['bh_sharpe']})")


def check(m: dict) -> dict:
    reasons = []
    tr, va = m["train"], m["val"]
    if tr["trades"] < MIN_TRADES:
        reasons.append("عدد صفقات قليل (نتيجة غير موثوقة)")
    if va["trades"] < MIN_VAL_TRADES:
        reasons.append(f"عدد صفقات قليل على التحقق ({va['trades']} < {MIN_VAL_TRADES})")
    if abs(tr["max_dd"]) > MAX_DD or abs(va["max_dd"]) > MAX_DD:
        reasons.append("سحب (Drawdown) أعلى من الحد")
    if va["sharpe"] < MIN_VAL_SHARPE:
        reasons.append("أداء ضعيف على بيانات التحقق")
    if tr["sharpe"] > 0 and va["sharpe"] < 0.5 * tr["sharpe"]:
        reasons.append("اشتباه Overfitting: التحقق أضعف بكثير من التدريب")
    _beats_benchmark(va, "التحقق", reasons)
    return {"passed": not reasons, "reasons": reasons}


def final_check(test: dict) -> dict:
    reasons = []
    if test["sharpe"] <= 0:
        reasons.append("خسارة/صفر على الاختبار النهائي")
    if abs(test["max_dd"]) > MAX_DD:
        reasons.append("Drawdown أعلى من الحد على الاختبار النهائي")
    if test["trades"] < MIN_TEST_TRADES:
        reasons.append(f"عدد صفقات قليل على الاختبار النهائي ({test['trades']} < {MIN_TEST_TRADES})")
    _beats_benchmark(test, "الاختبار النهائي", reasons)
    return {"passed": not reasons, "reasons": reasons}
