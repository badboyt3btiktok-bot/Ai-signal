"""اختبار منطق المدينة بنموذج LLM وهمي (بدون API): تخطيط، توظيف، مراجعة+إعادة، موافقات، تعلم مهارة، إيقاف طوارئ."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["CITY_HOME"] = tempfile.mkdtemp()
from city import llm, store
from city.city import City

R = llm.Resp
def text(s): return R(text=s, blocks=[{"type": "text", "text": s}], tokens=10)
def tool(_n, **inp):
    return R(tool_calls=[{"id": "x1", "name": _n, "input": inp}],
             blocks=[{"type": "tool_use", "id": "x1", "name": _n, "input": inp}], tokens=10)

class Fake:
    qa_seen = set()
    def chat(self, system, messages, tools=None, max_tokens=4000):
        if system.startswith("ROLE=CEO_PLAN"):
            return text(json.dumps({"tasks": [
                {"id": "t1", "title": "research", "description": "research X", "role": "researcher", "deps": []},
                {"id": "t2", "title": "model", "description": "build model", "role": "Data Scientist", "deps": ["t1"]},
                {"id": "t3", "title": "deploy", "description": "[SHELL] publish result", "role": "engineer", "deps": ["t2"]}]}))
        if system.startswith("ROLE=HR"):
            return text(json.dumps({"name": "data_scientist", "role": "data_scientist", "instructions": "stats expert",
                                    "tools": ["read_file", "write_file", "run_python"]}))
        if system.startswith("ROLE=CEO_SUMMARY"):
            return text(json.dumps({"summary": "كل شي تمام", "lessons": ["اختبر قبل التسليم"]}))
        name = system.split("You are ")[1].split(",")[0]
        first = messages[0]["content"]
        turn = len(messages) // 2
        if name == "qa":
            tid = first.split("VERIFY task ")[1].split(":")[0]
            if turn == 0: return tool("list_files")
            if tid == "t1" and tid not in Fake.qa_seen:
                Fake.qa_seen.add(tid)
                return text('نقص تفاصيل {"pass": false, "feedback": "add more detail"}')
            return text('{"pass": true, "feedback": ""}')
        tid = first.split("TASK ")[1].split(":")[0]
        if "[SHELL]" in first:
            return tool("shell", command="echo published") if turn == 0 else text("deployed")
        if turn == 0: return tool("write_file", path=f"{tid}.txt", content="result " + tid)
        if turn == 1 and name == "data_scientist": return tool("save_skill", name="model_recipe", description="how to model", content="steps")
        return text(f"{name} finished {tid}")

llm.set_backend(Fake())
c = City()
pid = c.add_request("test project")
assert c.run_project(pid) == "blocked", c.st["projects"][pid]["status"]
P = c.st["projects"][pid]
assert "data_scientist" in c.st["agents"], "HR should have hired"
assert [t["status"] for t in P["tasks"]] == ["done", "done", "blocked"]
assert P["tasks"][0]["attempts"] == 2, "QA retry expected"
assert os.path.exists(store.path("skills", "model_recipe.md")), "skill learned"
assert os.path.exists(store.path("workspace", pid, "t2.txt"))
assert "shell" not in c.st["agents"]["data_scientist"]["tools"], "least privilege"
c.decide("a1", True)
assert c.run_project(pid) == "done"
assert c.st["lessons"] == ["اختبر قبل التسليم"]
assert os.path.exists(store.path("workspace", pid, "REPORT.md"))
# kill switch
pid2 = c.add_request("second"); open(store.path("STOP"), "w").close()
assert c.run_project(pid2) == "paused_stop"; os.remove(store.path("STOP"))
# path escape blocked
from city import tools
ctx = tools.Ctx(c.st, P, P["tasks"][0], "x")
try: tools.read_file(ctx, {"path": "../../../../etc/passwd"}); raise SystemExit("ESCAPE!")
except PermissionError: pass
print("ALL TESTS PASSED")
