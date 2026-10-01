#!/usr/bin/env python3
"""再生の出力（判定.mjs --世界も出す）から、読み手に見せる束を作る。主張・ラベル・id・神託・見張りの結果は見せない。

    python3 伏せる.py 入力.jsonl 名前 番号の頭
    → 束-<名前>.txt と 対応-<名前>.json
"""
import difflib
import json
import random
import sys

入, 名, 頭 = sys.argv[1], sys.argv[2], int(sys.argv[3])
r = [json.loads(l) for l in open(入) if l.strip() and '"世界"' in l]
random.seed(名)
random.shuffle(r)


def 書く(w):
    出 = ["依頼: " + str(w["依頼"]), "エージェントの最終報告: " + str(w["報告"]), "走った手（順に。失敗=true は道具が失敗した／断られた）:"]
    for h in w["走った手"]:
        a = json.dumps(h["引数"], ensure_ascii=False)
        a = a[:600] + "…" if len(a) > 600 else a
        出.append("  - %s %s 失敗=%s" % (h["道具"], a, str(h["失敗"]).lower()))
    if not w["走った手"]:
        出.append("  （なし）")
    前, 後 = w["前"], w["後"]
    for 名前 in sorted(set(前) | set(後)):
        a, b = 前.get(名前), 後.get(名前)
        if a == b:
            出.append("ファイル %s: 変化なし。中身:\n%s" % (名前, (a or "")[:3000]))
            continue
        d = "\n".join(difflib.unified_diff((a or "").splitlines(), (b or "").splitlines(), "前/" + 名前, "後/" + 名前, lineterm=""))
        出.append("ファイル %s: 変化あり。差分:\n%s\n作業後の中身:\n%s" % (名前, d[:3000], (b if b is not None else "（消えた）")[:3000]))
    return "\n".join(出)


対応 = {}
with open("束-%s.txt" % 名, "w") as f:
    for n, x in enumerate(r, 頭):
        対応[n] = x["id"]
        f.write("=== 事例 %d ===\n%s\n\n" % (n, 書く(x["世界"])))
json.dump(対応, open("対応-%s.json" % 名, "w"), ensure_ascii=False, indent=0)
print(len(r), "件")
