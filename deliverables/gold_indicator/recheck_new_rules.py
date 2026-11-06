"""إعادة مرحلتي train/val بقواعد risk.py الجديدة (الاختبار النهائي ما بينلمس)."""
import json
from gold_toolkit import protocol, data, risk
old = json.load(open("results.json"))
pr = protocol.Protocol(data.from_yahoo(), lock_dir="__no_lock__")
from gold_toolkit import strategies
ok = 0
for r in old["stage2"]:
    pos = strategies.signal(r["template"], r["params"], pr.close)
    chk = pr.check(pos)
    ok += chk["passed"]
    va = pr.evaluate(pos)["val"]
    print(f"{r['template']:<14}{str(r['params']):<38} val S={va['sharpe']:>5} (B&H {va['bh_sharpe']}) tr={va['trades']:>2} "
          + ("PASS" if chk["passed"] else "FAIL: " + " | ".join(chk["reasons"])))
print(f"\npassed under new rules: {ok}/{len(old['stage2'])}")
try:
    pr.open_final("x", {}, strategies.signal("rsi_reversion", {"period": 20, "low": 40, "high": 70}, pr.close))
except protocol.FinalTestError as e:
    print("open_final refused:", str(e)[:150])
