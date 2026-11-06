"""بروتوكول التقييم الإلزامي: train/validation/final-test.

    from gold_toolkit import data, protocol, strategies
    pr = protocol.Protocol(data.from_yahoo())
    m = pr.evaluate(pos)                 # train + val فقط (الاختبار النهائي مخفي)
    chk = pr.check(pos)                  # risk.check
    res = pr.open_final("rsi_20_40_70", params, pos)   # مرة وحدة بس، وبس لاستراتيجية نجحت بـ check

- التقسيم ثابت (60/20/20 زمنياً) وما بيتغير.
- open_final بيرفض إذا الاستراتيجية فشلت بـ risk.check، وبيرفض أي فتح ثاني (final_test.lock بمجلد المشروع).
- المدينة بتراقب final_test.lock: أي حذف أو تعديل بعد أول فتح بينسجّل كمخالفة نزاهة بالتدقيق وبالتقرير.
"""
import datetime, json, os
from . import backtest, risk

TRAIN, VAL = 0.6, 0.8
LOCK = "final_test.lock"


class FinalTestError(RuntimeError):
    pass


class Protocol:
    def __init__(self, close, lock_dir="."):
        self.close = close
        n = len(close)
        self.seg = {"train": (0, int(n * TRAIN)), "val": (int(n * TRAIN), int(n * VAL)), "test": (int(n * VAL), n)}
        self.lock = os.path.join(lock_dir, LOCK)

    def dates(self):
        return {k: [str(self.close.index[i].date()), str(self.close.index[j - 1].date())]
                for k, (i, j) in self.seg.items()}

    def evaluate(self, pos):
        return {k: backtest.evaluate(self.close, pos, *self.seg[k]) for k in ("train", "val")}

    def check(self, pos):
        return risk.check(self.evaluate(pos))

    def final_opened(self):
        return os.path.exists(self.lock)

    def open_final(self, name, params, pos):
        if self.final_opened():
            raise FinalTestError("final test already opened once: " + open(self.lock, encoding="utf-8").read())
        chk = self.check(pos)
        if not chk["passed"]:
            raise FinalTestError("strategy failed risk.check; final test stays sealed: " + "; ".join(chk["reasons"]))
        te = backtest.evaluate(self.close, pos, *self.seg["test"])
        fc = risk.final_check(te)
        rec = {"strategy": name, "params": params, "opened": datetime.datetime.now().isoformat(timespec="seconds"),
               "segments": self.dates(), "test": te, "final_check": fc}
        with open(self.lock, "x", encoding="utf-8") as f:     # "x": بيفشل إذا الملف موجود
            json.dump(rec, f, ensure_ascii=False)
        return rec
