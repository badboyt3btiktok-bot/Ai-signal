import json
from gold_toolkit import data, protocol, strategies
w = json.load(open("winner.json"))
if w == "none":
    json.dump({"opened": False}, open("final.json", "w")); print("no winner; test stays sealed")
else:
    close = data.from_yahoo()
    pr = protocol.Protocol(close)
    rec = pr.open_final(w["name"], w["params"], strategies.signal(w["template"], w["params"], close))
    rec["opened_ok"] = True
    json.dump(rec, open("final.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(rec, ensure_ascii=False, indent=1))
