"""قلب المدينة: المدير (CEO) + HR (توظيف تلقائي) + مراجعة QA + تعافي ذاتي + ذاكرة دروس."""
import datetime, hashlib, json, os, re, time
from . import llm, store, tools
from .agent import Agent

MAX_TASKS, MAX_ATTEMPTS, MAX_ERRORS = 12, 2, 3
TOKEN_BUDGET = int(os.getenv("CITY_TOKEN_BUDGET", "600000"))
OWNER_LANG = os.getenv("CITY_OWNER_LANG", "Arabic (Levantine dialect)")


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _key(role):
    return re.sub(r"[^a-z0-9_]", "_", role.lower().strip())


class City:
    def __init__(self):
        store.init()
        self.st = store.load()
        for n, spec in store.DEFAULT_AGENTS.items():      # ترقية: أدوات جديدة للايجنت الأساسيين بالمدن القديمة
            if n in self.st["agents"]:
                have = self.st["agents"][n]["tools"]
                have += [t for t in spec["tools"] if t not in have]
        if not store.runner_alive():
            self.apply_inbox()

    def apply_inbox(self):
        """طبّق الأوامر اللي وصلت من الويب/CLI (موافقات، رفض، طلبات جديدة)."""
        done = 0
        for it in store.drain():
            try:
                if it["kind"] == "request":
                    self.add_request(it["text"])
                elif it["kind"] == "decision":
                    self.decide(it["id"], bool(it["ok"]))
                done += 1
            except Exception as e:
                store.audit("inbox_error", item=it, error=str(e)[:300])
        if done:
            self.save()
        return done

    def save(self):
        store.save(self.st)

    # ---------- استقبال الطلبات ----------
    def add_request(self, text):
        self.st["seq"] += 1
        pid = f"p{self.st['seq']}"
        self.st["projects"][pid] = {"id": pid, "request": text, "status": "queued", "tasks": [],
                                    "tokens": 0, "created": now(), "summary": ""}
        os.makedirs(store.path("workspace", pid), exist_ok=True)
        self.save()
        store.audit("request", project=pid, text=text)
        return pid

    # ---------- المدير: التخطيط ----------
    def roster(self):
        return "\n".join(f"- {n}: {a['role']} | {a['instructions'][:110]}" for n, a in self.st["agents"].items())

    def _charge(self, P, fn, *a):
        """أي نداء LLM باسم المشروع بينحسب عليه (تخطيط، ملخص...)."""
        t0, c0 = llm.TOTAL, llm.COST
        try:
            return fn(*a)
        finally:
            P["tokens"] += llm.TOTAL - t0
            P["cost_usd"] = round(P.get("cost_usd", 0) + llm.COST - c0, 4)

    def plan(self, P):
        return self._charge(P, self._plan, P)

    def _plan(self, P):
        j = llm.ask_json(
            "ROLE=CEO_PLAN\nYou are the CEO of an autonomous AI company. Break the owner's request into at most "
            f"{MAX_TASKS} concrete tasks forming a dependency graph. Assign each task to a role from the roster, or to a "
            "NEW role name if nobody fits (HR will hire one). Every task needs a verifiable deliverable (file or tested "
            'code). Return {"tasks":[{"id":"t1","title":"..","description":"..","role":"..","deps":[]}]}',
            f"Owner request:\n{P['request']}\n\nRoster:\n{self.roster()}\n\n"
            f"Company lessons:\n{chr(10).join(self.st['lessons'][-15:]) or '(none)'}\n\nSkills:\n{tools.skill_index()}")
        tasks = (j["tasks"] if isinstance(j, dict) else j)[:MAX_TASKS]
        ids = [t["id"] for t in tasks]
        assert len(set(ids)) == len(ids), "duplicate task ids"
        for t in tasks:
            assert all(d in ids and d != t["id"] for d in t.get("deps", [])), "bad deps"
        done, left = set(), list(tasks)           # فحص عدم وجود حلقات
        while left:
            ok = [t for t in left if set(t.get("deps", [])) <= done]
            assert ok, "cyclic dependencies"
            done |= {t["id"] for t in ok}
            left = [t for t in left if t not in ok]
        P["tasks"] = [{"id": t["id"], "title": t["title"], "description": t["description"],
                       "role": _key(t["role"]), "deps": t.get("deps", []), "status": "pending",
                       "attempts": 0, "output": "", "feedback": "", "agent": ""} for t in tasks]
        store.audit("planned", project=P["id"], tasks=[(t["id"], t["role"]) for t in P["tasks"]])

    # ---------- HR: توظيف ايجنت جديد عند الحاجة ----------
    def ensure_agent(self, role, task):
        ag = self.st["agents"]
        if role in ag:
            return role
        for n, a in ag.items():
            if a["role"] == role:
                return n
        try:
            s = llm.ask_json(
                "ROLE=HR\nYou are HR of an AI company. Design a new specialist agent. Return "
                '{"name":"snake_case","role":"snake_case","instructions":"2-4 sentences of expert guidance",'
                f'"tools":[subset of {list(tools.ALL)}]}}. Give least privilege; never give shell unless essential.',
                f"Needed role: {role}\nFirst task: {task['title']}\n{task['description']}")
        except Exception:
            s = {"instructions": f"You are an expert {role}. Deliver rigorous, verified work.", "tools": []}
        allowed = [t for t in s.get("tools", []) if t in tools.ALL] or ["read_file", "write_file", "list_files"]
        for must in ("save_skill", "list_skills", "load_skill", "request_approval"):
            if must not in allowed:
                allowed.append(must)
        ag[role] = {"role": role, "instructions": s["instructions"], "tools": allowed, "hired": now()}
        store.audit("hired", role=role, tools=allowed)
        return role

    # ---------- التنفيذ ----------
    def _t(self, P, tid):
        return next(t for t in P["tasks"] if t["id"] == tid)

    def review(self, P, t):
        qa = Agent("qa", self.st["agents"]["qa"])
        fake = {"id": f"{t['id']}-qa", "title": f"VERIFY task {t['id']}: {t['title']}",
                "description": f"Independently verify this deliverable. Original task: {t['description']}\n"
                               f"Worker's report: {t['output'][:2500]}\nInspect files, run code if relevant. "
                               'End your final message with one JSON line: {"pass": true|false, "feedback": "..."}'}
        res = qa.run(self.st, P, fake, {}, over_budget=lambda: self._over(P))
        return self.verdict(res["output"])

    @staticmethod
    def verdict(text):
        """آخر كائن JSON فيه "pass" (بيتحمل أقواس جوا الـ feedback وأسطر متعددة)."""
        vs = [o for o in llm.json_objects(text) if isinstance(o, dict) and "pass" in o]
        if not vs:
            return {"pass": False, "feedback": "QA verdict unclear; make deliverables easier to verify."}
        v = vs[-1]
        p = v["pass"]
        return {"pass": p is True or str(p).lower() == "true", "feedback": str(v.get("feedback", ""))}

    def recover(self, P, t):
        try:
            j = llm.ask_json(
                "ROLE=CEO_RECOVER\nA task failed repeatedly. Rewrite it so it can succeed (smaller scope, different "
                'approach, or a different role). Return {"description":"..","role":".."}',
                f"Task: {t['title']}\n{t['description']}\nFeedback: {t['feedback']}\nRoster:\n{self.roster()}")
            t["description"], t["role"] = j["description"], _key(j.get("role", t["role"]))
        except Exception:
            pass
        t.update(recovered=True, attempts=0, status="pending")
        store.audit("recovered", project=P["id"], task=t["id"])

    def _over(self, P):
        """هل المشروع تجاوز سقف التوكنز؟ (بيحسب كمان التوكنز اللي انصرفت جوا المهمة الحالية)."""
        return P["tokens"] + (llm.TOTAL - self._task_t0 if self._task_t0 is not None else 0) > TOKEN_BUDGET

    _task_t0 = None

    def exec_task(self, P, t):
        store.verify_protected()
        before, c0 = llm.TOTAL, llm.COST
        self._task_t0 = before
        try:
            self._exec_task(P, t)
            P["errors"] = 0
        except Exception as e:
            # خطأ API/شبكة بنص المهمة: رجّعها pending بدل ما تعلق "running" للأبد
            t["status"], t["attempts"] = "pending", max(0, t["attempts"] - 1)
            P["errors"] = P.get("errors", 0) + 1
            store.audit("task_error", project=P["id"], task=t["id"], error=f"{type(e).__name__}: {e}"[:500])
            raise
        finally:
            self.watch_final_lock(P)
            self._task_t0 = None
            P["tokens"] += llm.TOTAL - before
            P["cost_usd"] = round(P.get("cost_usd", 0) + llm.COST - c0, 4)
            store.audit("task", project=P["id"], task=t["id"], agent=t["agent"], status=t["status"],
                        tokens=llm.TOTAL - before)

    def watch_final_lock(self, P):
        """final_test.lock لازم ينكتب مرة وحدة وما يتغير. أي حذف/تعديل = مخالفة نزاهة (بتنسجّل وبتطلع بالتقرير)."""
        f = store.path("workspace", P["id"], "final_test.lock")
        h = hashlib.sha256(open(f, "rb").read()).hexdigest() if os.path.exists(f) else None
        old = P.get("final_lock")
        if old is None and h:
            P["final_lock"] = h
            store.audit("final_test_opened", project=P["id"], content=open(f, encoding="utf-8").read()[:2000])
        elif old and h != old:
            msg = "final_test.lock deleted" if h is None else "final_test.lock modified"
            P.setdefault("integrity", []).append(f"{now()} {msg}: final test may have been reopened")
            store.audit("integrity_violation", project=P["id"], detail=msg)
            P["final_lock"] = h or old

    def _exec_task(self, P, t):
        t["agent"] = self.ensure_agent(t["role"], t)
        t["status"], t["attempts"] = "running", t["attempts"] + 1
        deps = {d: self._t(P, d)["output"] for d in t["deps"]}
        res = Agent(t["agent"], self.st["agents"][t["agent"]]).run(self.st, P, t, deps,
                                                                   over_budget=lambda: self._over(P))
        t["output"] = res["output"]
        if res["status"] == "blocked":
            t["status"], t["attempts"] = "blocked", t["attempts"] - 1
        elif res["status"] in ("stopped", "budget"):
            t["status"], t["attempts"] = "pending", t["attempts"] - 1
        else:
            v = self.review(P, t) if res["status"] == "ok" else {"pass": False, "feedback": res["output"][-500:]}
            if self._over(P) and not v.get("pass"):
                t["status"] = "pending"          # QA انقطع بسبب السقف: لا تحسبها محاولة فاشلة
                t["attempts"] -= 1
                return
            if v.get("pass"):
                t["status"] = "done"
            else:
                t["feedback"] = v.get("feedback", "")
                if t["attempts"] < MAX_ATTEMPTS:
                    t["status"] = "pending"
                elif not t.get("recovered"):
                    self.recover(P, t)
                else:
                    t["status"] = "failed"

    def run_project(self, pid):
        P = self.st["projects"][pid]
        if not P["tasks"]:
            self.plan(P)
        for t in P["tasks"]:                     # مهمة علقت "running" لأن العملية انقتلت فجأة (في مشغّل واحد بس)
            if t["status"] == "running":
                t["status"], t["attempts"] = "pending", max(0, t["attempts"] - 1)
                store.audit("task_reset", project=P["id"], task=t["id"])
        P["status"], P["errors"] = "running", 0
        self.save()
        while True:
            if store.killed():
                P["status"] = "paused_stop"
                break
            if P["tokens"] > TOKEN_BUDGET:
                P["status"] = "paused_budget"
                break
            if P.get("errors", 0) >= MAX_ERRORS:
                P["status"] = "paused_error"     # أخطاء متتالية (API/شبكة): run يدوي بيستأنف
                break
            self.apply_inbox()                       # موافقات وصلت وقت الشغل
            ready = [t for t in P["tasks"] if t["status"] == "pending"
                     and all(self._t(P, d)["status"] == "done" for d in t["deps"])]
            if not ready:
                break
            try:
                self.exec_task(P, ready[0])
            except Exception as e:
                print(f"[{P['id']}] task {ready[0]['id']} error (will retry): {type(e).__name__}: {e}")
            self.save()
        ts = [t["status"] for t in P["tasks"]]
        if P["status"] == "running":
            if all(s == "done" for s in ts):
                self._charge(P, self.finish, P)
            elif "blocked" in ts:
                P["status"] = "blocked"
            else:
                P["status"] = "needs_attention"
        self.save()
        return P["status"]

    def finish(self, P):
        digest = "\n".join(f"{t['id']} [{t['agent']}] {t['title']}: {t['output'][:500]}" for t in P["tasks"])
        try:
            j = llm.ask_json(
                f"ROLE=CEO_SUMMARY\nYou are the CEO. Write the final report to the owner in {OWNER_LANG}: what was delivered, "
                "where the files are, honest caveats. Also extract up to 3 reusable lessons for the company. "
                'Return {"summary":"..","lessons":["..",".."]}',
                f"Request: {P['request']}\n\nTasks:\n{digest}")
            P["summary"] = j["summary"]
            self.st["lessons"] = (self.st["lessons"] + j.get("lessons", []))[-40:]
        except Exception:
            P["summary"] = digest
        P["status"] = "done"
        warn = "".join(f"\n- ⚠️ {x}" for x in P.get("integrity", []))
        if warn:
            P["summary"] += "\n\nتحذيرات نزاهة (من المدينة، مش من الايجنت):" + warn
        open(store.path("workspace", P["id"], "REPORT.md"), "w", encoding="utf-8").write(
            f"# {P['request']}\n\n{P['summary']}\n")

    # ---------- موافقات المالك ----------
    def decide(self, aid, ok):
        a = self.st["approvals"].get(aid)
        if not a or a["status"] != "pending":
            raise ValueError(f"no pending approval {aid}")
        a["status"] = "approved" if ok else "denied"
        P = self.st["projects"][a["project"]]
        t = self._t(P, a["task"])
        if t["status"] == "blocked":
            t["status"] = "pending"
            t["feedback"] = (t["feedback"] + f"\nOwner {'APPROVED' if ok else 'DENIED'}: {a['action']} {a['details']}").strip()
        if P["status"] == "blocked":
            P["status"] = "queued"
        self.save()
        store.audit("approval", id=aid, approved=ok)

    # ---------- التشغيل المستمر ----------
    def run_all(self, resume=("queued", "paused_stop", "paused_budget", "paused_error"), claim=True):
        if claim:
            store.claim_runner()
        try:
            self._run_all(resume)
        finally:
            if claim:
                store.release_runner()

    def _run_all(self, resume):
        self.apply_inbox()
        for pid, P in list(self.st["projects"].items()):
            if P["status"] in resume:
                try:
                    print(f"[{pid}] {self.run_project(pid)}")
                except Exception as e:
                    P["status"] = "needs_attention"
                    P["summary"] = f"CEO error: {e}"
                    self.save()
                    print(f"[{pid}] error: {e}")

    def serve(self, interval=5):
        print("المدينة شغالة. أضف طلبات من terminal ثاني: python agentcity.py add \"...\"  (Ctrl+C للإيقاف)")
        store.claim_runner()
        try:
            while True:
                self.st = store.load()
                self.apply_inbox()
                if not store.killed():
                    self.run_all(resume=("queued", "paused_stop"), claim=False)   # budget/error بدهم قرار المالك
                time.sleep(interval)
        finally:
            store.release_runner()
