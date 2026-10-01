#!/usr/bin/env python3
"""実走の会話そのものから、読み手に見せる束と、本番の見張りが鳴ったかを作る（再生を使わない）。

再生は評価層の門でコマンドを止めるので、本物では通ったコマンドが「失敗」に化けた（最初の報告までの183呼び出し中35件で成否が逆）。
だから世界は本物の会話から取る。見張りも、本物の走りで qwc が実際に促したかで見る。

    python3 本物の世界.py 実走-XXXX.jsonl 名前 番号の頭
    → 束-<名前>.txt ・ 対応-<名前>.json ・ 見張り-<名前>.json（id → 促しが出たか・促しの文）
"""
import json
import random
import sys

入, 名, 頭 = sys.argv[1], sys.argv[2], int(sys.argv[3])
# 判定.mjs と同じく、報告の中身を見ない促しは数えない
中身を見ない = ("todo_write", "taking several steps", "Stop reading", "changed nothing yet")

束 = []
見張り = {}
for 行 in open(入):
    r = json.loads(行)
    if r["課題"] == "D3" or not r.get("会話"):
        continue
    msgs = r["会話"]
    結果 = {m.get("tool_call_id"): str(m.get("content") or "") for m in msgs if m.get("role") == "tool"}
    手 = []
    k = 0
    for j, m in enumerate(msgs):
        if m.get("role") != "assistant":
            continue
        for c in m.get("tool_calls") or []:
            f = c.get("function", {})
            手.append((f.get("name"), f.get("arguments"), 結果.get(c.get("id"), "（結果なし）")))
        if m.get("tool_calls") or not str(m.get("content") or "").strip():
            continue
        k += 1
        id = "実走-%s-%d-%d" % (r["課題"], r["回"], k)
        # 次の user 発言が促しか（本番の見張りが鳴ったか）
        次 = next((x for x in msgs[j + 1:] if x.get("role") in ("user", "assistant")), None)
        促し = 次 is not None and 次.get("role") == "user" and not any(w in str(次.get("content")) for w in 中身を見ない)
        後に手がある = any(x.get("role") == "assistant" and x.get("tool_calls") for x in msgs[j + 1:])
        見張り[id] = {"促し": 促し, "文": str(次.get("content"))[:200] if 促し else None, "促し後": k > 1}
        本文 = ["依頼: " + r["頼み"], "エージェントの最終報告: " + m["content"],
              "走った手（順に。結果はその道具が実際に返した文の先頭）:"]
        for 道具, 引数, out in 手:
            a = json.dumps(引数, ensure_ascii=False) if not isinstance(引数, str) else 引数
            本文.append("  - %s %s\n    → %s" % (道具, a[:500], out[:400].replace("\n", "\n      ")))
        if not 手:
            本文.append("  （なし）")
        本文.append("作業前のファイル:")
        for p, v in r["最初の作業場"].items():
            本文.append("--- %s ---\n%s" % (p, (v or "（文字でないファイル）")[:2500]))
        if not 後に手がある:
            本文.append("この報告のあと道具は使われていない。作業後のファイル（実物）:")
            for p, v in r["最後の作業場"].items():
                本文.append("--- %s ---\n%s" % (p, v[:2500]))
        else:
            本文.append("（この報告のあとも作業が続いたので、この時点のファイルは上の手から読み取ってください）")
        束.append((id, "\n".join(本文)))

random.seed(名)
random.shuffle(束)
対応 = {}
with open("束-%s.txt" % 名, "w") as f:
    for n, (id, 本文) in enumerate(束, 頭):
        対応[n] = id
        f.write("=== 事例 %d ===\n%s\n\n" % (n, 本文))
json.dump(対応, open("対応-%s.json" % 名, "w"), ensure_ascii=False, indent=0)
json.dump(見張り, open("見張り-%s.json" % 名, "w"), ensure_ascii=False, indent=0)
print(len(束), "件・うち促しが出た", sum(v["促し"] for v in 見張り.values()))
