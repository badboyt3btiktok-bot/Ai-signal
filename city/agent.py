from . import llm, store, tools

MAX_STEPS = 25
MAX_TRUNCATIONS = 3        # كم مرة متتالية مسموح الرد ينقطع عند max_tokens قبل ما نوقف المهمة


class Agent:
    def __init__(self, name, spec):
        self.name, self.spec = name, spec

    def system(self, st):
        lessons = "\n".join(f"- {l}" for l in st["lessons"][-15:]) or "(none yet)"
        return (f"You are {self.name}, a {self.spec['role']} inside Agent City, an autonomous AI company. "
                f"The owner only talks to the CEO. You work independently and never ask the owner questions.\n"
                f"{self.spec['instructions']}\n\nRULES:\n"
                "- Produce concrete deliverables as files in your workspace. Never fake results: run code to verify.\n"
                "- Before starting, check list_skills; if a skill fits, load_skill and use it.\n"
                "- If you figure out a reusable technique, call save_skill so the whole city learns it.\n"
                "- Irreversible or external actions (spending, sending messages, deploying, deleting) need request_approval.\n"
                "- Keep each tool call small: write big files in several write_file calls (append=true).\n"
                "- Finish with a short summary: what you did, which files, caveats.\n\n"
                f"SKILLS:\n{tools.skill_index()}\n\nCOMPANY LESSONS:\n{lessons}")

    def prompt(self, project, task, deps):
        d = "\n".join(f"[{k}] {str(v)[:1500]}" for k, v in deps.items()) or "(none)"
        fb = f"\nQA/CEO feedback to address:\n{task['feedback']}" if task.get("feedback") else ""
        return (f"PROJECT REQUEST: {project['request']}\n\nTASK {task['id']}: {task['title']}\n{task['description']}\n"
                f"\nOutputs of dependency tasks:\n{d}{fb}\n\nYour workspace is workspace/{project['id']}/ "
                f"(shared libraries are in ../shared/).")

    def run(self, st, project, task, deps, over_budget=lambda: False):
        ctx = tools.Ctx(st, project, task, self.name)
        names = [t for t in self.spec["tools"] if t in tools.ALL]
        schemas = tools.schemas(names)
        system = self.system(st)        # ثابت طول المهمة: شرط للـ prompt caching
        messages = [{"role": "user", "content": self.prompt(project, task, deps)}]
        out, truncs = "", 0
        for step in range(MAX_STEPS):
            if store.killed():
                return {"status": "stopped", "output": out}
            if over_budget():
                return {"status": "budget", "output": out + "\n[token budget exceeded]"}
            resp = llm.chat(system, messages, schemas)
            # التاريخ append-only: البلوكات بترجع زي ما هي (thinking/text/tool_use)
            messages.append({"role": "assistant", "content": resp.blocks or [{"type": "text", "text": "..."}]})
            out = resp.text or out
            if resp.stop_reason == "refusal":
                store.audit("refusal", agent=self.name, project=project["id"], task=task["id"])
                return {"status": "error", "output": out + "\n[model refused this request]"}
            if not resp.tool_calls:
                return {"status": "ok", "output": out, "steps": step + 1}
            if resp.stop_reason == "max_tokens":
                # tool_use مقطوع: مدخلاته ناقصة. ما بننفذه، وكل tool_use لازم ياخد tool_result
                truncs += 1
                store.audit("truncated", agent=self.name, project=project["id"], task=task["id"])
                if truncs >= MAX_TRUNCATIONS:
                    return {"status": "error", "output": out + "\n[responses kept hitting max_tokens]"}
                messages.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": c["id"], "is_error": True,
                     "content": "NOT EXECUTED: your response hit max_tokens and this tool input was cut off. "
                                "Split the work: write files in smaller chunks (write_file with append=true)."}
                    for c in resp.tool_calls]})
                continue
            truncs = 0
            results = []
            for c in resp.tool_calls:
                err = False
                try:
                    r = tools.call(ctx, c["name"], c["input"], names)
                except Exception as e:
                    r, err = f"ERROR: {type(e).__name__}: {e}", True
                store.audit("tool", agent=self.name, project=project["id"], task=task["id"], tool=c["name"],
                            error=err)
                res = {"type": "tool_result", "tool_use_id": c["id"], "content": str(r)[:8000] or "(no output)"}
                if err:
                    res["is_error"] = True
                results.append(res)
            messages.append({"role": "user", "content": results})
            if ctx.blocked:
                return {"status": "blocked", "output": ctx.block_reason}
        return {"status": "error", "output": out + "\n[step limit reached]"}
