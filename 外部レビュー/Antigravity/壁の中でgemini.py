#!/usr/bin/env python3
"""Gemini CLI を guardrun の壁の中で、確認なし（--yolo）で走らせる。書けるのは作業フォルダと ~/.gemini だけ。

    python3 壁の中でgemini.py <作業フォルダ> <頼みのファイル> [壁時計秒]
"""
import json, os, sys, time
sys.path.insert(0, os.path.expanduser("~/bin"))
import guardrun as g
H = os.path.expanduser
w, 頼みf = os.path.abspath(sys.argv[1]), sys.argv[2]
秒 = int(sys.argv[3]) if len(sys.argv) > 3 else 1800
env = dict(os.environ, GEMINI_API_KEY=open(H("~/.gemini-api-key")).read().strip())
argv = ["/opt/homebrew/bin/gemini", "--skip-trust", "--yolo", "--output-format", "json", "-p", open(頼みf).read()]
記録 = H("~/Antigravity作業/記録-%s" % time.strftime("%m%d-%H%M"))
os.makedirs(記録, exist_ok=True)
r = g.run(argv, w, 記録=記録, enforcer=g.SandboxExec(), prove=False, wall_sec=秒,
          max_file_bytes=500_000_000, max_add_bytes=500_000_000, max_add_files=5000, env=env,
          extra_writes=[H("~/.gemini")], extra_reads=["/opt/homebrew"], net_allow=["*:443"])
open(os.path.join(記録, "出力.txt"), "w").write(r.get("_出力") or "")
print(json.dumps({k: r.get(k) for k in ("判定", "終了コード", "壁に当たった", "理由", "差分")}, ensure_ascii=False, indent=1)[:3000])
print("記録:", 記録)
