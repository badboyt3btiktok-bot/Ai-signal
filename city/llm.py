import json, os, re
from dataclasses import dataclass, field

MODEL = os.getenv("CITY_MODEL", "claude-sonnet-5-5")
EFFORT = os.getenv("CITY_EFFORT", "medium")          # low|medium|high|xhigh|max ("" = API default)
FALLBACKS = os.getenv("CITY_FALLBACKS", "1") != "0"  # server-side refusal fallback (beta)
MAX_TOKENS = int(os.getenv("CITY_MAX_TOKENS", "16000"))
TOTAL = 0          # عداد توكنز عام (لميزانية المشاريع): input + cache_write + cache_read + output
COST = 0.0         # تقدير تكلفة بالدولار
_backend = None

# $/1M tokens: (input, output). cache write = 1.25x input, cache read = 0.1x input
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0), "claude-haiku-5-5": (0.10, 0.50),
          "claude-fable-5-1": (10.0, 50.0)}


@dataclass
class Resp:
    text: str = ""
    tool_calls: list = field(default_factory=list)   # [{id,name,input}]
    blocks: list = field(default_factory=list)       # محتوى الرد كما هو (thinking/text/tool_use) بصيغة dicts
    tokens: int = 0
    stop_reason: str = "end_turn"
    cost: float = 0.0


def usage_cost(model, inp, cw, cr, out):
    pi, po = PRICES.get(model, PRICES["claude-sonnet-5-5"])
    return (inp * pi + cw * pi * 1.25 + cr * pi * 0.1 + out * po) / 1e6


class AnthropicBackend:
    def __init__(self):
        from anthropic import Anthropic
        self.c = Anthropic(max_retries=6)
        self.fallbacks = FALLBACKS

    def _create(self, kw):
        import anthropic
        if self.fallbacks:
            try:
                return self.c.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
            except anthropic.BadRequestError as e:
                if "fallback" not in str(e).lower():
                    raise
                self.fallbacks = False      # الحساب/المنصة ما بتدعمها: كمّل بدونها
        return self.c.messages.create(**kw)

    def chat(self, system, messages, tools=None, max_tokens=None):
        kw = dict(model=MODEL, max_tokens=max_tokens or MAX_TOKENS, system=system, messages=messages,
                  cache_control={"type": "ephemeral"})   # prompt caching تلقائي لآخر بلوك قابل للكاش
        if EFFORT:
            kw["output_config"] = {"effort": EFFORT}
        if tools:
            kw["tools"] = tools
        r = self._create(kw)
        u = r.usage
        cw, cr = (getattr(u, "cache_creation_input_tokens", 0) or 0), (getattr(u, "cache_read_input_tokens", 0) or 0)
        out = Resp(tokens=u.input_tokens + cw + cr + u.output_tokens, stop_reason=r.stop_reason or "end_turn",
                   cost=usage_cost(MODEL, u.input_tokens, cw, cr, u.output_tokens))
        for b in r.content:
            # لازم نرجّع كل البلوكات زي ما هي (خصوصاً thinking مع signature) وإلا الـ API بيعتبر التاريخ معدّل
            d = b.model_dump(mode="json", exclude_none=True)
            if d.get("type") == "text":
                if not d.get("text"):
                    continue                     # بلوك نص فاضي بيرفضه الـ API لما يرجع بالتاريخ
                out.text += d["text"]
            elif d.get("type") == "tool_use":
                out.tool_calls.append({"id": d["id"], "name": d["name"], "input": d.get("input") or {}})
            elif d.get("type") == "fallback":
                continue                         # علامة تحويل نموذج، مش محتوى
            out.blocks.append(d)
        return out


def set_backend(b):
    global _backend
    _backend = b


def get():
    global _backend
    if _backend is None:
        if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
            raise SystemExit("لازم تحط ANTHROPIC_API_KEY بالبيئة.")
        _backend = AnthropicBackend()
    return _backend


def chat(system, messages, tools=None, max_tokens=None):
    global TOTAL, COST
    r = get().chat(system, messages, tools, max_tokens)
    TOTAL += r.tokens
    COST += r.cost
    return r


def json_objects(text):
    """كل كائنات/مصفوفات JSON الصالحة بالنص بالترتيب (بتتحمل نص قبل/بعد، fences، وأقواس داخل strings)."""
    dec, out, i = json.JSONDecoder(), [], 0
    text = text or ""
    while i < len(text):
        if text[i] in "{[":
            try:
                obj, end = dec.raw_decode(text, i)
                out.append(obj)
                i = end
                continue
            except ValueError:
                pass
        i += 1
    return out


def parse_json(text):
    """أكبر كائن JSON بالنص (الرد الأساسي، مش أمثلة صغيرة جواته)."""
    objs = json_objects(text)
    if not objs:
        raise ValueError("no JSON found in model output")
    return max(objs, key=lambda o: len(json.dumps(o, ensure_ascii=False)))


def ask_json(system, user, max_tokens=8000, retries=1):
    sys_ = system + "\nReturn ONLY valid JSON, no markdown fences, no prose."
    msgs = [{"role": "user", "content": user}]
    for attempt in range(retries + 1):
        r = chat(sys_, msgs, None, max_tokens)
        try:
            if r.stop_reason == "max_tokens":
                raise ValueError("output was truncated at max_tokens; be more concise")
            return parse_json(r.text)
        except ValueError as e:
            if attempt == retries:
                raise
            msgs = msgs + [{"role": "assistant", "content": r.blocks or [{"type": "text", "text": "(empty)"}]},
                           {"role": "user", "content": f"Your reply could not be parsed ({e}). "
                                                       "Reply again with ONLY the complete, valid JSON."}]
