"""حلقة مطوّر/مدقق بين نموذجين: Gemini بيكتب الكود، Claude بيراجعه بعد تشغيله بـ sandbox.

التشغيل:
    pip install anthropic google-genai
    export GEMINI_API_KEY=... ANTHROPIC_API_KEY=...
    python ai_pair.py "اكتب سكربت بيحسب مجموع أرقام قائمة وبيسجل أوقات التنفيذ بملف log"

ملاحظة أمان: الكود اللي بيكتبه النموذج بينفّذ على جهازك. التنفيذ هون بمجلد مؤقت منفصل
وبوضع بايثون معزول (-I) ومع timeout، بس هاد مش عزل حقيقي (فيه شبكة ووصول لملفاتك).
للعزل الحقيقي حط AI_PAIR_DOCKER=1 (بيستعمل docker run --network none).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Callable

GEMINI_MODEL = os.environ.get("AI_PAIR_GEMINI_MODEL", "gemini-2.5-flash")
CLAUDE_MODEL = os.environ.get("AI_PAIR_CLAUDE_MODEL", "claude-sonnet-5-5")
EXEC_TIMEOUT = int(os.environ.get("AI_PAIR_TIMEOUT", "12"))
MAX_LOG_CHARS = 6000  # ما نبعت سجلات ضخمة للمدقق

# ---------------------------------------------------------------- النماذج

def make_gemini_developer() -> Callable[[str], str]:
    from google import genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def dev(prompt: str) -> str:
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return resp.text or ""  # .text ممكن تكون None إذا انحجب الرد
    return dev


def make_claude_auditor() -> Callable[[str], str]:
    from anthropic import Anthropic
    client = Anthropic()  # بيقرأ ANTHROPIC_API_KEY لحاله

    def audit(prompt: str) -> str:
        resp = client.messages.create(
            model=CLAUDE_MODEL, max_tokens=2048,
            system=AUDITOR_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        # content[0] مش دايماً text: نجمع كل كتل النص
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return audit

# ---------------------------------------------------------------- التعليمات

DEVELOPER_SYSTEM = """أنت مهندس برمجة (Lead Developer).
اكتب سكربت بايثون واحد مكتمل يشتغل فوراً بدون إدخال من المستخدم وبدون مكتبات خارج المكتبة القياسية.
لازم السكربت يطبع نتائجه، ويختبر نفسه بـ assert على حالات حدّية، وينتهي بـ exit code 0 إذا كل شي سليم.
ضع الكود كامل داخل كتلة ```python واحدة فقط."""

AUDITOR_SYSTEM = """أنت مدقق برمجيات (Senior Code Auditor).
بتستلم المهمة والكود وسجل التنفيذ الحقيقي. افحص: صحة النتيجة، الحالات الحدّية، الأخطاء، الأداء، وتحقيق كل متطلبات المهمة.
أول سطر من ردك لازم يكون بالضبط واحد من:
VERDICT: APPROVED
VERDICT: REJECTED
إذا REJECTED، اكتب بعده نقاط إصلاح محددة وقصيرة للمطور."""

# ---------------------------------------------------------------- أدوات

_FENCE = re.compile(r"```[ \t]*(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_python(raw: str) -> str:
    """أطول كتلة كود بالرد (النموذج أحياناً بيحط أمثلة صغيرة قبل الكود الأساسي)."""
    blocks = _FENCE.findall(raw or "")
    if blocks:
        return max(blocks, key=len).strip()
    return (raw or "").strip()


_VERDICT = re.compile(r"^\s*\**\s*VERDICT\s*:\s*\**\s*(APPROVED|REJECTED)\b", re.IGNORECASE | re.MULTILINE)


def parse_verdict(feedback: str) -> bool:
    """True فقط لما المدقق يقول APPROVED صراحة. "NOT APPROVED" ما بتنحسب موافقة."""
    m = _VERDICT.search(feedback or "")
    if m:
        return m.group(1).upper() == "APPROVED"
    # رد بدون الصيغة المطلوبة: نقبل فقط إذا الرد كله كلمة APPROVED
    return (feedback or "").strip().strip(".*` ").upper() == "APPROVED"


@dataclass
class ExecResult:
    ok: bool
    returncode: int | None
    stdout: str
    stderr: str
    files: dict[str, str] = field(default_factory=dict)  # ملفات نصية انكتبت (مثل log)

    def report(self) -> str:
        def clip(s: str) -> str:
            return s if len(s) <= MAX_LOG_CHARS else s[:MAX_LOG_CHARS] + "\n...[مقطوع]"
        parts = [f"exit code: {self.returncode}", f"--- stdout ---\n{clip(self.stdout) or '(فاضي)'}",
                 f"--- stderr ---\n{clip(self.stderr) or '(فاضي)'}"]
        for name, body in self.files.items():
            parts.append(f"--- ملف ناتج: {name} ---\n{clip(body)}")
        return "\n".join(parts)


def execute_in_sandbox(code: str, timeout: int = EXEC_TIMEOUT) -> ExecResult:
    """تنفيذ بمجلد مؤقت خاص بكل جولة، وبنفس مفسّر بايثون الحالي، مع التقاط stdout و stderr سوا."""
    workdir = tempfile.mkdtemp(prefix="ai_pair_")
    try:
        path = os.path.join(workdir, "main.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        if os.environ.get("AI_PAIR_DOCKER") == "1" and shutil.which("docker"):
            cmd = ["docker", "run", "--rm", "--network", "none", "--memory", "512m",
                   "-v", f"{workdir}:/work", "-w", "/work", "python:3.13-slim", "python", "-I", "main.py"]
        else:
            cmd = [sys.executable, "-I", "main.py"]
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"}  # بدون مفاتيح API
        try:
            r = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True,
                               timeout=timeout, env=env, stdin=subprocess.DEVNULL)
            rc, out, err = r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired as e:
            rc = None
            out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            err = f"TIMEOUT: تجاوز التنفيذ {timeout} ثانية"
        files = {}
        for name in sorted(os.listdir(workdir)):
            p = os.path.join(workdir, name)
            if name != "main.py" and os.path.isfile(p) and os.path.getsize(p) < 200_000:
                with open(p, encoding="utf-8", errors="replace") as f:
                    files[name] = f.read()
        return ExecResult(ok=(rc == 0), returncode=rc, stdout=out, stderr=err, files=files)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

# ---------------------------------------------------------------- الحلقة


def run_ai_to_ai_pipeline(task: str, max_rounds: int = 5,
                          developer: Callable[[str], str] | None = None,
                          auditor: Callable[[str], str] | None = None,
                          log: Callable[[str], None] = print) -> str | None:
    developer = developer or make_gemini_developer()
    auditor = auditor or make_claude_auditor()

    log(f"🚀 [بدء]: {task}\n")
    code = extract_python(developer(f"{DEVELOPER_SYSTEM}\n\nالمهمة: {task}"))

    for round_num in range(1, max_rounds + 1):
        log(f"🔄 [الجولة {round_num}]: تشغيل الكود بالـ sandbox...")
        if not code:
            result = ExecResult(False, None, "", "المطور ما رجّع أي كود.")
        else:
            result = execute_in_sandbox(code)
        log(f"   exit code = {result.returncode}")

        feedback = auditor(
            f"المهمة المطلوبة:\n{task}\n\nالكود الحالي:\n```python\n{code}\n```\n\n"
            f"سجل التنفيذ الحقيقي:\n{result.report()}"
        )
        approved = parse_verdict(feedback)

        if approved and result.ok:
            log("\n✅ [تم الاعتماد]: الكود اشتغل بنجاح والمدقق وافق.")
            log("-" * 40 + f"\n{code}\n" + "-" * 40)
            return code

        if approved and not result.ok:
            # المدقق وافق بس التنفيذ فشل: الحقيقة هي سجل التنفيذ، مش رأي النموذج
            feedback = ("المدقق وافق لكن التنفيذ فشل، لذلك الكود مرفوض.\n" + result.report())

        log(f"⚠️ [ملاحظات المدقق]:\n{feedback.strip()}\n")
        if round_num == max_rounds:
            break
        log("🧠 [إعادة للمطور للإصلاح]...")
        code = extract_python(developer(
            f"{DEVELOPER_SYSTEM}\n\nالمهمة: {task}\n\n"
            f"الكود السابق:\n```python\n{code}\n```\n\n"
            f"سجل التنفيذ:\n{result.report()}\n\n"
            f"ملاحظات المدقق:\n{feedback}\n\n"
            "أصلح كل النقاط واكتب الكود المعدل كاملاً."
        ))

    log("\n❌ [فشل]: وصلنا للحد الأقصى من الجولات بدون كود معتمد.")
    return None


if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) or "اكتب سكربت بيحسب مجموع أرقام قائمة، وبيسجل أوقات التنفيذ بملف log"
    sys.exit(0 if run_ai_to_ai_pipeline(task) else 1)
