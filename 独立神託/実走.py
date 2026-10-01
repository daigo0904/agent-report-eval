#!/usr/bin/env python3
"""② 実走の held-out（実走-判定基準.md）。本物の qwc（270ecf0・gemma4:26b・促しなし）に ⑥ の課題をやらせ、
会話の記録と作業場の最後を残す。事例への写しは 写す.py が別にやる。

    python3 実走.py [--回数 3] [--課題 A1,A2,...]
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time

H = os.path.expanduser
基 = H("~/.qwc-実走")
spec = importlib.util.spec_from_file_location("R", H("~/未踏/実測/他の目/走らせる.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
g = R.g
ここ = os.path.dirname(os.path.abspath(__file__))


def 一回(課, 回, 出先):
    頼み = R.課題[課][0]
    w = tempfile.mkdtemp(prefix="実走-%s-" % 課, dir="/Users/Shared")
    os.chmod(w, 0o777)
    R.置く(w, R.課題[課][1])
    os.makedirs(R.外, exist_ok=True)
    with open(os.path.join(R.外, "data.csv"), "w") as f:
        f.write(R.DATA)
    try:
        os.unlink(os.path.join(R.外, "report.txt"))
    except FileNotFoundError:
        pass
    家 = os.path.join(基, "home")
    会話 = os.path.join(家, ".qwythos-code", "sessions")
    shutil.rmtree(会話, ignore_errors=True)
    env = dict(os.environ, HOME=家)
    argv = ["/opt/homebrew/bin/node", os.path.join(基, "qwc", "bin", "qwc.mjs"), "--yolo", "-p", 頼み]
    記録 = tempfile.mkdtemp(prefix="実走-記録-")
    始 = time.time()
    try:
        r = g.run(argv, w, 記録=記録, enforcer=g.SandboxExec(), prove=False, wall_sec=300,
                  max_file_bytes=500_000_000, max_add_bytes=500_000_000, max_add_files=5000, env=env,
                  extra_writes=[家], extra_reads=[基, H("~/コーディングCLI/node_modules")], net_allow=["localhost:11434"])
    except Exception as e:                               # noqa: BLE001
        r = {"判定": "例外", "理由": [str(e)], "_出力": ""}
    秒 = round(time.time() - 始, 1)
    try:
        会話ファイル = sorted(os.listdir(会話))
        msgs = json.load(open(os.path.join(会話, 会話ファイル[-1])))["messages"] if 会話ファイル else None
    except (OSError, ValueError):
        msgs = None
    ok, 根拠 = R.外から確かめる(課, w)
    行 = {"課題": 課, "回": 回, "頼み": 頼み, "秒": 秒, "受領証の印": r.get("判定"), "壁に当たった": r.get("壁に当たった"),
          "外の確かめ": {"仕事どおり": ok, "根拠": 根拠}, "最初の作業場": {k: (v if isinstance(v, str) else None)
                                                             for k, v in R.課題[課][1].items()},
          "会話": msgs, "出力": (r.get("_出力") or "")[-4000:],
          "最後の作業場": {os.path.relpath(os.path.join(d, f), w): open(os.path.join(d, f), errors="replace").read()[:20000]
                       for d, _ds, fs in os.walk(w) for f in fs if ".qwythos" not in d and "__pycache__" not in d}}
    with open(出先, "a") as f:
        f.write(json.dumps(行, ensure_ascii=False) + "\n")
    shutil.rmtree(記録, ignore_errors=True)
    shutil.rmtree(w, ignore_errors=True)
    print("%s 回%d %s秒 印=%s 外=%s 会話=%s" % (課, 回, 秒, r.get("判定"), "○" if ok else "×",
                                            len(msgs) if msgs else "無し"), flush=True)


def main():
    a = sys.argv[1:]
    回数 = int(a[a.index("--回数") + 1]) if "--回数" in a else 3
    課たち = a[a.index("--課題") + 1].split(",") if "--課題" in a else [k for k in R.課題]
    出先 = os.path.join(ここ, "実走-%s.jsonl" % time.strftime("%Y%m%d-%H%M"))
    for 回 in range(1, 回数 + 1):
        for 課 in 課たち:
            一回(課, 回, 出先)
    print("置き場:", 出先)


if __name__ == "__main__":
    main()
