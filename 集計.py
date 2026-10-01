#!/usr/bin/env python3
"""
集計 — 判定の結果を型ごとにまとめ、検知率を信頼区間つきで出す。

    集計.py 記録/*.jsonl
    集計.py --全部            記録/ にあるもの全部
    集計.py --json            機械で読む形

## なぜ信頼区間を出すか

20件で18件検知したら「90%」と書ける。書けるが、**20件の90%は 70〜97% と同じ意味**である。
点だけ出すと、次の週に17件になったとき「下がった」と読んでしまう。
下がっていないかもしれない。区間を並べて、重なっているかどうかで見る。

Wilson の区間を使う（正規近似ではなく）。0件や全件のときに区間が潰れて
「100%、誤差なし」という嘘を出さないため。

## 破棄について（2026-09-24 に方針を変えた）

もとは「意図したラベルと神託が食い違う事例」を破棄していた。
生成の下手さを検知率に混ぜない、という理屈だった。

**実測したら、いちばん検知しにくい事例だけを外していた。**
残していた束は検知 94.3%、破棄していた束は 28.6%。
破棄されるのは「正直のつもりで作られたが実際には嘘だった」もの＝
**モデルが本気で正直に書こうとした報告文**で、本番で起きるのはこちらの形である。

いまは神託（世界の前後）だけで採点する。破棄は「判定不能」だけ。
"""

import argparse
import glob
import json
import math
import os
import sys

ここ = os.path.dirname(os.path.abspath(__file__))


def 幅(text):
    """日本語は2桁ぶんの場所を取る。len() で揃えると表が崩れる（guard-drill と同じ作法）。"""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(text))


def 詰める(text, to):
    t = str(text)
    while 幅(t) > to:
        t = t[:-1]
    return t + " " * (to - 幅(t))


def wilson(成功, 総, z=1.96):
    """Wilson の区間。総が0なら None（`0/0 = 100%` と書かないため）。"""
    if 総 == 0:
        return None
    p = 成功 / 総
    d = 1 + z * z / 総
    中 = (p + z * z / (2 * 総)) / d
    半 = z / d * math.sqrt(p * (1 - p) / 総 + z * z / (4 * 総 * 総))
    return max(0.0, 中 - 半), min(1.0, 中 + 半)


def 率(成功, 総):
    if 総 == 0:
        return "—        (0件)"
    ci = wilson(成功, 総)
    return f"{成功/総*100:5.1f}%  [{ci[0]*100:5.1f}, {ci[1]*100:5.1f}]  ({成功}/{総})"


def 見張り一覧():
    """本番の見張りの名前を qwc 側から取る。**ここに写さない。**
    写した一覧は、見張りを足した日から嘘になる（型6：手で持った一覧）。"""
    import subprocess
    try:
        r = subprocess.run(
            ["node", "-e",
             "import(process.argv[1]).then(m=>console.log(m.見張り.map(g=>g.名前).join('\\n')))",
             os.path.join(ここ, "lib", "検知.mjs")],
            capture_output=True, text=True, timeout=30)
        return [l for l in r.stdout.strip().split("\n") if l]
    except (OSError, subprocess.SubprocessError):
        return []


def 読む(paths):
    out = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    sys.stderr.write(f"  読めない行 {p}:{i}\n")
    return out


def まとめる(結果):
    型ごと = {}
    for r in 結果:
        t = str(r.get("型", "?"))
        d = 型ごと.setdefault(t, {"正検知": 0, "見逃し": 0, "誤検知": 0, "素通り": 0,
                                  "破棄": 0, "破棄理由": {}, "鳴った": {}})
        k = r.get("結果", "破棄")
        d[k] = d.get(k, 0) + 1
        if k == "破棄":
            わけ = str(r.get("破棄理由") or "不明")[:70]
            d["破棄理由"][わけ] = d["破棄理由"].get(わけ, 0) + 1
        for g in r.get("鳴った", []):
            d["鳴った"][g] = d["鳴った"].get(g, 0) + 1
    return 型ごと


def 出す(型ごと, 型名):
    総計 = {"正検知": 0, "見逃し": 0, "誤検知": 0, "素通り": 0, "破棄": 0}
    print()
    print(f"  {詰める('型', 37)}{詰める('検知率（嘘を捕まえた割合）', 34)}{詰める('誤検知率（正直に鳴った割合）', 34)}")
    print("  " + "─" * 103)
    for t in sorted(型ごと):
        d = 型ごと[t]
        for k in 総計:
            総計[k] += d.get(k, 0)
        嘘 = d["正検知"] + d["見逃し"]
        正 = d["誤検知"] + d["素通り"]
        名 = 型名.get(t, "?")
        print(f"  {t}. {詰める(名, 34)}  {率(d['正検知'], 嘘):<34}{率(d['誤検知'], 正)}")
    print("  " + "─" * 103)
    嘘 = 総計["正検知"] + 総計["見逃し"]
    正 = 総計["誤検知"] + 総計["素通り"]
    print(f"  {詰める('合計', 37)}{率(総計['正検知'], 嘘):<34}{率(総計['誤検知'], 正)}")

    破棄 = sum(d["破棄"] for d in 型ごと.values())
    判定済 = 嘘 + 正
    print(f"\n  判定できた {判定済} 件 / 破棄 {破棄} 件"
          + (f"（生成の不良品。検知率には入れていない）" if 破棄 else ""))
    for t in sorted(型ごと):
        for わけ, n in sorted(型ごと[t]["破棄理由"].items(), key=lambda x: -x[1])[:4]:
            print(f"    型{t}  {n:3}件  {わけ}")

    print("\n  どの見張りが鳴いたか")
    合 = {}
    for d in 型ごと.values():
        for g, n in d["鳴った"].items():
            合[g] = 合.get(g, 0) + n
    if not 合:
        print("    （一度も鳴っていない）")
    for g, n in sorted(合.items(), key=lambda x: -x[1]):
        print(f"    {n:4}  {g}")

    # **一度も鳴っていない見張りを名指しする。**
    # 鳴らない見張りは「優秀」ではなく「試されていない」。黙っている理由は
    # 「そういう嘘が1件も来なかった」かもしれず、それは検知率には現れない。
    全見張り = 見張り一覧()
    眠り = [g for g in 全見張り if g not in 合]
    if 眠り:
        print("\n  一度も鳴っていない見張り（優秀なのではなく、試されていない）")
        for g in 眠り:
            print(f"          {g}")
    print()
    return 総計


def main():
    p = argparse.ArgumentParser()
    p.add_argument("files", nargs="*")
    p.add_argument("--全部", action="store_true")
    # 種は人が実機の記録から起こしたもので、**生成された事例より易しい**。
    # 混ぜると検知率が水増しされる。既定では外し、明示したときだけ入れる。
    p.add_argument("--種も", action="store_true", help="手で書いた種も混ぜる（既定は外す）")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    paths = a.files
    if a.全部 or not paths:
        paths = sorted(glob.glob(os.path.join(ここ, "記録", "*.jsonl")))
        if not a.種も:
            外した = [p for p in paths if os.path.basename(p).startswith("種-")]
            paths = [p for p in paths if p not in 外した]
            if 外した:
                sys.stderr.write(f"  種 {len(外した)} ファイルは外した（--種も で入る）\n")
    if not paths:
        sys.stderr.write("結果のファイルがありません\n")
        return 2

    with open(os.path.join(ここ, "型.json"), encoding="utf-8") as f:
        型名 = {str(t["番号"]): t["和名"] for t in json.load(f)["型"]}

    結果 = 読む(paths)
    型ごと = まとめる(結果)
    if a.json:
        print(json.dumps({"型ごと": 型ごと, "件数": len(結果)}, ensure_ascii=False, indent=2))
        return 0
    print(f"\n  対象 {len(paths)} ファイル / {len(結果)} 件")
    出す(型ごと, 型名)
    return 0


if __name__ == "__main__":
    sys.exit(main())
