"""اختبار ai_pair.py بنماذج وهمية (بدون API)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ai_pair as ap

GOOD = '''import logging, time
logging.basicConfig(filename="run.log", level=logging.INFO)
t = time.perf_counter()
total = sum([1, 2, 3])
logging.info("sum=%s took=%.6f", total, time.perf_counter() - t)
assert total == 6
print(total)
'''
BAD = "print(sum([1, 2, '3']))"

# extraction
assert ap.extract_python("hi\n```python\nx=1\n```\nbye") == "x=1"
assert ap.extract_python("```py\na\n```\n```python\nlonger = 2\n```") == "longer = 2"
assert ap.extract_python("```\ny=2\n```") == "y=2"
assert ap.extract_python("z=3") == "z=3"
assert ap.extract_python(None) == ""

# verdict: "NOT APPROVED" must not count as approval (bug in the original)
assert ap.parse_verdict("VERDICT: APPROVED")
assert ap.parse_verdict("**VERDICT: APPROVED**\nlooks good")
assert not ap.parse_verdict("VERDICT: REJECTED\nthis is not APPROVED")
assert not ap.parse_verdict("NOT APPROVED: fix the bug")
assert ap.parse_verdict("APPROVED")

# sandbox
r = ap.execute_in_sandbox(GOOD)
assert r.ok and r.stdout.strip() == "6" and "sum=6" in r.files["run.log"], r.report()
r = ap.execute_in_sandbox(BAD)
assert not r.ok and "TypeError" in r.stderr
r = ap.execute_in_sandbox("import time; print('start', flush=True); time.sleep(5)", timeout=1)
assert not r.ok and r.returncode is None and "TIMEOUT" in r.stderr
r = ap.execute_in_sandbox("import os; print(os.environ.get('ANTHROPIC_API_KEY'))")
assert r.stdout.strip() == "None"  # keys don't leak into model-written code

# loop: bad code first, then fixed after review
def fake_dev():
    outs = iter([f"```python\n{BAD}\n```", f"here:\n```python\n{GOOD}\n```"])
    return lambda prompt: next(outs)
seen = []
def fake_auditor(prompt):
    seen.append(prompt)
    return "VERDICT: REJECTED\nTypeError" if "TypeError" in prompt else "VERDICT: APPROVED"
out = ap.run_ai_to_ai_pipeline("sum", 3, fake_dev(), fake_auditor, log=lambda s: None)
assert out == GOOD.strip() and len(seen) == 2

# auditor approves but execution fails -> not accepted
out = ap.run_ai_to_ai_pipeline("sum", 2, lambda p: f"```python\n{BAD}\n```",
                               lambda p: "VERDICT: APPROVED", log=lambda s: None)
assert out is None

# developer returns nothing -> no crash, just rejection
out = ap.run_ai_to_ai_pipeline("sum", 1, lambda p: "", lambda p: "VERDICT: REJECTED", log=lambda s: None)
assert out is None

print("ai_pair: all tests passed")
