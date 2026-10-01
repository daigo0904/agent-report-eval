#!/usr/bin/env python3
"""
実行 — 生成 → 判定 → 集計 を1回まわす。定時に呼ばれる形でも、常駐でも動く。

    実行.py                  1回まわす（launchd / cron から呼ぶのはこれ）
    実行.py --件 3           ラベルごとに3件ずつ作る
    実行.py --間隔 900       常駐して15分おきにまわす
    実行.py --生成なし       すでにある事例を判定し直すだけ（見張りを直した日に使う）

## 型7 への備え（訓練自身が途中で打ち切られる）

guard-drill は 2026-09-13 まで、1項目落ちた時点で打ち切っていた。
05:30 の定時実行は3番目の spin で落ちていたので、**後ろの11項目が毎日ずっと
走っていなかった**。緑でも赤でもなく、そもそも試されていない状態だった。

この層は同じ型を扱うのだから、同じ罠を踏んではいけない。

1. 1件落ちても残りを走らせる（生成も判定も、件ごとに try で囲む）
2. **試みた数と終えた数を必ず別々に出す。** 終えた数だけ出すと、
   途中で落ちた日に件数が静かに減るだけで、誰も気づかない
3. 落ちたことは記録に残し、心拍は残す（guardlib の Guard.run がやる）

## 推論サーバは1つしかない

ollama は待ち行列が1本で、外の依頼が1つ走るだけで数百秒ずれる。
この層は 24 時間まわる前提なので、**譲るほうを既定にする**。
qwc や音声アシスタントが動いていたら、その回は何もしない。
（この見分けは当てにならない。プロセス名が出ていないことは、
  ollama が空いていることの証明ではない。**譲り損ねることはある**。）
"""

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.expanduser("~/bin"))
from guardlib import Guard, maintenance                   # noqa: E402

ここ = os.path.dirname(os.path.abspath(__file__))
G = Guard("eval-loop")

# この人たちが動いていたら譲る。**居ないことは、空いていることの証明ではない。**
#
# ■ openclaw を入れてはいけない（実測で確かめた）
#   最初は入れていた。ところが openclaw の gateway は常駐で、いつ見ても居る。
#   入れた状態で1回走らせたら、初回から「譲りました」で何もせずに終わった。
#   **毎回きちんと譲って、毎回きちんと心拍を残して、一度も仕事をしない。**
#   これは譲る相手の選び方の問題で、ここもこの層が扱っている型そのもの。
#   譲るのは「長い依頼を抱えている最中の人」だけにする。
譲る相手 = ["qwythos-code/bin/qwc", "voice-ai"]


def 誰か使っている():
    for 名 in 譲る相手:
        try:
            r = subprocess.run(["pgrep", "-f", 名], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        pids = [p for p in r.stdout.split() if p and int(p) != os.getpid()]
        if pids:
            return 名
    return None


def 走らせる(argv, 秒, 名):
    """外の道具を1つ呼ぶ。落ちても投げずに返す（1件で全体を止めないため）。"""
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=秒, cwd=ここ)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"{名} が {秒} 秒で終わらなかった"
    except OSError as e:
        return 127, "", f"{名} を呼べない: {e}"


def 一回(件, 生成する, 型=None):
    結果 = {"試み": 0, "終え": 0, "生成": 0, "判定": 0}

    事例ファイル = None
    if 生成する:
        結果["試み"] += 1
        argv = [sys.executable, os.path.join(ここ, "生成.py"), "--件", str(件)]
        if 型:
            argv += ["--型", str(型)]
        # 1件あたり最大3分 × 型3つ × ラベル2つ × 件数 ＋ 余白
        秒 = 180 * 3 * 2 * 件 + 120
        code, out, err = 走らせる(argv, 秒, "生成")
        G.log(f"生成 → 終了コード {code}\n{err.strip()[-2000:]}")
        if code == 0 and out.strip():
            事例ファイル = out.strip().splitlines()[-1]
            結果["終え"] += 1
            try:
                with open(事例ファイル, encoding="utf-8") as f:
                    結果["生成"] = sum(1 for l in f if l.strip())
            except OSError:
                pass
        else:
            # 生成が落ちても判定には進む。**すでにある事例は判定できる。**
            G.log("生成が落ちたので、この回は既存の事例だけを判定する")

    # 判定の対象。生成した分があればそれ、無ければ未判定のものを拾う
    対象 = [事例ファイル] if 事例ファイル else 未判定の事例()
    if not 対象:
        G.log("判定する事例が無い")
        return 結果

    os.makedirs(os.path.join(ここ, "記録"), exist_ok=True)
    for f in 対象:
        結果["試み"] += 1
        名 = os.path.basename(f)
        出し先 = os.path.join(ここ, "記録", 名)
        code, out, err = 走らせる(["node", os.path.join(ここ, "判定.mjs"), f], 1800, "判定")
        if out.strip():
            with open(出し先, "w", encoding="utf-8") as g:
                g.write(out)
            結果["判定"] += sum(1 for l in out.splitlines() if l.strip())
            結果["終え"] += 1
        G.log(f"判定 {名} → 終了コード {code}\n{err.strip()[-2000:]}")
    return 結果


def 未判定の事例():
    事例 = os.path.join(ここ, "事例")
    記録 = os.path.join(ここ, "記録")
    if not os.path.isdir(事例):
        return []
    済 = set(os.listdir(記録)) if os.path.isdir(記録) else set()
    return [os.path.join(事例, f) for f in sorted(os.listdir(事例))
            if f.endswith(".jsonl") and f not in 済]


def 集計を出す():
    code, out, err = 走らせる([sys.executable, os.path.join(ここ, "集計.py"), "--全部"], 120, "集計")
    if out:
        sys.stdout.write(out)
        # 集計そのものも記録に残す。あとから「あの日いくつだったか」を辿れるように
        try:
            with open(os.path.join(ここ, "記録", "集計.log"), "a", encoding="utf-8") as f:
                f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n{out}")
        except OSError:
            pass
    if err:
        sys.stderr.write(err)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--件", type=int, default=2, help="ラベルごとの生成件数")
    p.add_argument("--型", default=None)
    p.add_argument("--間隔", type=int, default=0, help="秒。0 なら1回で終わる")
    p.add_argument("--生成なし", action="store_true")
    p.add_argument("--譲らない", action="store_true", help="ほかが動いていても走る")
    a = p.parse_args()

    回 = 0
    while True:
        回 += 1
        # **(そうか, 説明) の2つ組が返る。**受け取りを間違えると、
        # 組は常に真なので「毎回、手入れ中なので何もしない」になる。
        # 心拍は出るしログも健康に見えるので、外からは働いているのと区別が付かない
        # ——この層が扱っている型そのもの。書いた直後に1回走らせて見つけた。
        止め, わけ = maintenance()
        if 止め:
            G.log(f"手を出さない印が出ているので、この回は何もしない（{わけ}）")
        else:
            使用中 = None if a.譲らない else 誰か使っている()
            if 使用中:
                G.log(f"{使用中} が動いているので譲る")
                sys.stderr.write(f"  {使用中} が動いているので、この回は譲りました\n")
            else:
                r = 一回(a.件, not a.生成なし, a.型)
                G.log(f"試み {r['試み']} / 終え {r['終え']} / 生成 {r['生成']} 件 / 判定 {r['判定']} 件")
                sys.stderr.write(
                    f"  {回} 回目: 試み {r['試み']} / 終え {r['終え']}"
                    f" / 生成 {r['生成']} 件 / 判定 {r['判定']} 件\n")
                集計を出す()
        if not a.間隔:
            return 0
        time.sleep(a.間隔)


if __name__ == "__main__":
    sys.exit(G.run(main))
