#!/usr/bin/env python3
"""実走の会話を評価層の事例の形に写す（実走-判定基準.md）。

    python3 写す.py 実走-XXXX.jsonl > ../事例/J1-実走-gemma4.jsonl

道具を呼ばずに終わった assistant の発言を、すべて報告として1件ずつ事例にする。
手 = その発言までに qwc が出した道具の呼び出し全部。主張・ラベル・型は付けない（正解は独立の読み手が付ける）。
D3（Shift_JIS のバイト）は事例の形（文字列）で作業場を表せないので写さない。
"""
import json
import sys

for 行 in open(sys.argv[1]):
    r = json.loads(行)
    if r["課題"] == "D3" or not r.get("会話"):
        print("写さない: %s 回%d（%s）" % (r["課題"], r["回"], "D3" if r["課題"] == "D3" else "会話なし"), file=sys.stderr)
        continue
    作業場 = {k: v for k, v in r["最初の作業場"].items() if v is not None}
    手 = []
    k = 0
    for m in r["会話"]:
        if m.get("role") != "assistant":
            continue
        for c in m.get("tool_calls") or []:
            f = c.get("function", {})
            引数 = f.get("arguments")
            if isinstance(引数, str):
                try:
                    引数 = json.loads(引数)
                except ValueError:
                    引数 = {"_生": 引数}
            手.append({"道具": f.get("name"), "引数": 引数 or {}})
        if not m.get("tool_calls") and str(m.get("content") or "").strip():
            k += 1
            print(json.dumps({
                "作業場": 作業場, "依頼": r["頼み"], "手": list(手), "報告": m["content"],
                "id": "実走-%s-%d-%d" % (r["課題"], r["回"], k), "型": "実走", "ラベル": None,
                "主張": [], "実走": {"課題": r["課題"], "回": r["回"], "何番目の報告": k, "促し後": k > 1,
                                  "外の確かめ": r["外の確かめ"], "受領証の印": r["受領証の印"],
                                  "最後の報告か": None}
            }, ensure_ascii=False))
