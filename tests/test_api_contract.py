"""اختبار انحدار لأخطاء ظهرت بمقارنة الكود مع سلوك Claude API الحقيقي (بدون مفتاح):
- الـ backend الحقيقي (AnthropicBackend) مع client وهمي بيرجّع كائنات SDK حقيقية (thinking/text/tool_use).
- كل طلب بيتفحص بقواعد الـ API: كل tool_use لازم ياخد tool_result بالرسالة التالية، ممنوع بلوك نص فاضي،
  التاريخ append-only (thinking blocks بترجع زي ما هي)، والـ system ثابت طول المهمة.
- max_tokens بنص tool_use، refusal، JSON مع أقواس، سقف توكنز جوا المهمة، خطأ API بنص المهمة، حماية risk.py."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["CITY_HOME"] = tempfile.mkdtemp()
from anthropic.types import Message
from city import llm, store, tools
from city import city as citymod
from city.agent import Agent
from city.city import City


def msg(content, stop="end_turn", inp=1000, out=200, cr=0):
    return Message.model_validate({"id": "m", "type": "message", "role": "assistant", "model": llm.MODEL,
                                   "content": content, "stop_reason": stop, "stop_sequence": None,
                                   "usage": {"input_tokens": inp, "output_tokens": out,
                                             "cache_creation_input_tokens": 0, "cache_read_input_tokens": cr}})


def think(): return {"type": "thinking", "thinking": "", "signature": "sig-abc"}
def txt(s): return {"type": "text", "text": s}
def use(i, n, **inp): return {"type": "tool_use", "id": i, "name": n, "input": inp}


class ContractClient:
    """client وهمي بيطبق قواعد الـ API وبيرجّع ردود مبرمجة مسبقاً."""
    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.messages = self.beta = self   # client.messages.create و client.beta.messages.create

    def create(self, **kw):
        kw.pop("betas", None); kw.pop("fallbacks", None)
        self.check(kw)
        self.calls.append(json.loads(json.dumps(kw, default=str)))
        r = self.script.pop(0)
        if isinstance(r, Exception):
            raise r
        self.returned = (len(kw["messages"]), kw["system"], r.model_dump(mode="json", exclude_none=True)["content"])
        return r

    def check(self, kw):
        m = kw["messages"]
        assert m[0]["role"] == "user"
        for i, x in enumerate(m):
            if isinstance(x["content"], list):
                for b in x["content"]:
                    assert not (b.get("type") == "text" and not b.get("text")), "empty text block -> 400"
                    assert b.get("type") != "tool_result" or b.get("content"), "empty tool_result"
            if x["role"] == "assistant" and isinstance(x["content"], list):
                ids = {b["id"] for b in x["content"] if b.get("type") == "tool_use"}
                if ids:
                    assert i + 1 < len(m), "tool_use without following tool_result -> 400"
                    got = {b["tool_use_id"] for b in m[i + 1]["content"] if b.get("type") == "tool_result"}
                    assert ids == got, f"tool_use ids {ids} != tool_result ids {got} -> 400"
        if self.calls and self.calls[-1]["system"] == kw["system"]:
            prev = self.calls[-1]["messages"]
            now = json.loads(json.dumps(m, default=str))
            assert now[:len(prev)] == prev, "history edited (thinking blocks dropped?) -> preserved-thinking 400"
        if getattr(self, "returned", None) and self.returned[1] == kw["system"] and len(m) > self.returned[0]:
            sent = json.loads(json.dumps(m[self.returned[0]]["content"], default=str))
            exp = [b for b in self.returned[2] if not (b.get("type") == "text" and not b.get("text"))]
            assert sent == exp, "assistant turn not echoed verbatim (thinking dropped?) -> preserved-thinking 400"
        assert kw.get("cache_control") == {"type": "ephemeral"}, "prompt caching off"
        assert kw["max_tokens"] >= 8000, "max_tokens too low (truncation)"


def backend(script):
    b = llm.AnthropicBackend.__new__(llm.AnthropicBackend)
    b.c, b.fallbacks = ContractClient(script), True
    llm.set_backend(b)
    return b.c


store.init()
c = City()
pid = c.add_request("contract test")
P = c.st["projects"][pid]
task = {"id": "t1", "title": "write", "description": "write a file", "deps": [], "feedback": ""}

# 1) thinking blocks محفوظة + max_tokens بنص tool_use ما بيتنفذ + is_error
cl = backend([
    msg([think(), use("u1", "write_file", path="big.py")], stop="max_tokens"),   # مدخلات ناقصة (بدون content)
    msg([think(), use("u2", "write_file", path="big.py", content="print(1)\n")], stop="tool_use"),
    msg([think(), use("u3", "write_file", path="big.py", content="print(2)\n", append="true")], stop="tool_use"),
    msg([think(), use("u4", "read_file", path="nope.txt")], stop="tool_use"),
    msg([think(), txt("done: big.py")]),
])
r = Agent("engineer", c.st["agents"]["engineer"]).run(c.st, P, task, {})
assert r["status"] == "ok" and r["output"] == "done: big.py", r
assert open(store.path("workspace", pid, "big.py")).read() == "print(1)\nprint(2)\n", "append chunks"
second = cl.calls[1]["messages"]
assert second[1]["content"][0]["type"] == "thinking" and second[1]["content"][0]["signature"] == "sig-abc"
tr = second[2]["content"][0]
assert tr["is_error"] and "NOT EXECUTED" in tr["content"], "truncated tool_use must not run"
last = cl.calls[4]["messages"][-1]["content"][0]
assert last["is_error"] is True and "FileNotFoundError" in last["content"], "tool errors flagged is_error"
assert len({x["system"] for x in cl.calls}) == 1, "system prompt must stay frozen during a task"

# 2) refusal -> المهمة بتوقف بدون تنفيذ أدوات
backend([msg([use("u1", "write_file", path="x.py", content="x")], stop="refusal")])
r = Agent("engineer", c.st["agents"]["engineer"]).run(c.st, P, dict(task, id="t2"), {})
assert r["status"] == "error" and "refused" in r["output"]
assert not os.path.exists(store.path("workspace", pid, "x.py")), "refused turn tools must not run"

# 3) حلقة max_tokens متكررة بتوقف بدل ما تكمّل لحد 25 خطوة
backend([msg([use(f"u{i}", "write_file", path="y.py")], stop="max_tokens") for i in range(10)])
r = Agent("engineer", c.st["agents"]["engineer"]).run(c.st, P, dict(task, id="t3"), {})
assert r["status"] == "error" and "max_tokens" in r["output"]

# 4) توكنز: cache reads بتنحسب، والكلفة بتتقدّر
llm.TOTAL = 0; llm.COST = 0.0
backend([msg([txt("hi")], inp=100, out=50, cr=900)])
llm.chat("s", [{"role": "user", "content": "x"}])
assert llm.TOTAL == 1050 and llm.COST > 0

# 5) JSON: نص قبل/بعد، fences، أقواس داخل strings، ورد مقطوع بيتعاد مرة
assert llm.parse_json('Sure!\n```json\n{"tasks":[{"id":"t1","description":"use {x} here"}]}\n```') == \
    {"tasks": [{"id": "t1", "description": "use {x} here"}]}
backend([msg([txt('{"tasks": [')], stop="max_tokens"), msg([txt('{"ok": true}')])])
assert llm.ask_json("ROLE=X", "y") == {"ok": True}
v = City.verdict('checked. feedback mentions dict {a: 1}\n{"pass": false, "feedback": "fix {x}\\nand y"}')
assert v == {"pass": False, "feedback": "fix {x}\nand y"}, v
assert City.verdict('{"pass": "true", "feedback": ""}')["pass"] is True
assert City.verdict("no verdict here")["pass"] is False

# 6) سقف التوكنز بينفرض جوا المهمة، مش بس بين المهام
citymod.TOKEN_BUDGET = 5000
pid2 = c.add_request("budget test")
P2 = c.st["projects"][pid2]
P2["tasks"] = [{"id": "t1", "title": "loop", "description": "d", "role": "engineer", "deps": [], "status": "pending",
                "attempts": 0, "output": "", "feedback": "", "agent": ""}]
backend([msg([use(f"u{i}", "list_files")], stop="tool_use", inp=2000) for i in range(25)])
assert c.run_project(pid2) == "paused_budget"
assert P2["tokens"] < 5000 + 2200 * 2, P2["tokens"]
assert P2["tasks"][0]["status"] == "pending" and P2["tasks"][0]["attempts"] == 0
citymod.TOKEN_BUDGET = 600000

# 7) خطأ API بنص المهمة: المهمة ما بتعلق "running"، وبعد 3 أخطاء المشروع paused_error
import anthropic, httpx2 as httpx
err = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
pid3 = c.add_request("error test")
P3 = c.st["projects"][pid3]
P3["tasks"] = [dict(P2["tasks"][0], status="pending", attempts=0)]
backend([err, err, err])
assert c.run_project(pid3) == "paused_error"
assert P3["tasks"][0]["status"] == "pending" and P3["tasks"][0]["attempts"] == 0

# 8) أدوات المخاطر محمية: write_file مرفوض، وأي تعديل بكود مولّد بيرجع من الـ seed
ctx = tools.Ctx(c.st, P, task, "engineer")
risk = store.path("workspace", "shared", "gold_toolkit", "risk.py")
try:
    tools.write_file(ctx, {"path": "../shared/gold_toolkit/risk.py", "content": "MAX_DD = 9"}); raise SystemExit("risk.py writable!")
except PermissionError:
    pass
tools.write_file(ctx, {"path": "../shared/gold_toolkit/my_strats.py", "content": "# new strategy ok"})
open(risk, "w").write("MAX_DD = 9")          # كأن run_python عدّله
assert store.verify_protected() == [os.path.join("workspace", "shared", "gold_toolkit", "risk.py")]
assert "MAX_DD = 0.30" in open(risk).read()

# 9) run_python بيورث proxy/CA (عشان yfinance) بس مش مفتاح API
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:9"; os.environ["ANTHROPIC_API_KEY"] = "sk-secret"
env = tools._env(ctx)
assert env["HTTPS_PROXY"] == "http://127.0.0.1:9" and "ANTHROPIC_API_KEY" not in env
print("ALL API-CONTRACT TESTS PASSED")
