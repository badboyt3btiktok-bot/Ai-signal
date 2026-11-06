"""ايجنت المخاطر (قواعد صارمة بالكود، مش رأي LLM). أي استراتيجية بتفشل هون بتنرفض."""
MIN_TRADES = 10
MAX_DD = 0.30
MIN_VAL_SHARPE = 0.3

# تنبيه: ما في أي كود تنفيذ صفقات حقيقية بهالمشروع. الإشارات فقط.
LIVE_TRADING = False


def check(m: dict) -> dict:
    reasons = []
    tr, va = m["train"], m["val"]
    if tr["trades"] < MIN_TRADES:
        reasons.append("عدد صفقات قليل (نتيجة غير موثوقة)")
    if abs(tr["max_dd"]) > MAX_DD or abs(va["max_dd"]) > MAX_DD:
        reasons.append("سحب (Drawdown) أعلى من الحد")
    if va["sharpe"] < MIN_VAL_SHARPE:
        reasons.append("أداء ضعيف على بيانات التحقق")
    if tr["sharpe"] > 0 and va["sharpe"] < 0.5 * tr["sharpe"]:
        reasons.append("اشتباه Overfitting: التحقق أضعف بكثير من التدريب")
    return {"passed": not reasons, "reasons": reasons}


def final_check(test: dict) -> dict:
    reasons = []
    if test["sharpe"] <= 0:
        reasons.append("خسارة/صفر على الاختبار النهائي")
    if abs(test["max_dd"]) > MAX_DD:
        reasons.append("Drawdown أعلى من الحد على الاختبار النهائي")
    return {"passed": not reasons, "reasons": reasons}
