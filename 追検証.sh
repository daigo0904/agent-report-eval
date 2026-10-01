#!/bin/zsh
# 追検証 — 時間切れで取り切れなかった qwen3 を、上限を延ばして取り直す。
#   ⑤（別モデルが書いた嘘）が6件しか無く、そこだけ何も言えないため。
set -u
cd ~/評価層
記=記録/追検証-$(date +%Y%m%d-%H%M%S).log
言(){ echo "[$(date +%H:%M:%S)] $*" | tee -a $記 }

言 "qwen3 を取り直す（上限600秒）"
python3 -c "
import sys,os; sys.path.insert(0,os.path.expanduser('~/bin'))
from guardlib import maintenance_hold
maintenance_hold('別モデルの追検証（評価層）', 10800, by='eval-crossmodel')
print('手入れの印を置いた（3時間）')" | tee -a $記

言 "D1 qwen3 の束（型1-3・各7件＝42件）"
python3 生成.py --モデル qwen3:14b-q4_K_M --件 7 --出し先 事例/D1-束-qwen3.jsonl >>$記 2>&1
言 "D2 qwen3 の対照（型10・24件）"
python3 生成.py --モデル qwen3:14b-q4_K_M --型 10 --件 24 --出し先 事例/D2-対照-qwen3.jsonl >>$記 2>&1
言 "D3 qwen2.5-coder の対照を厚くする（型10・18件）"
python3 生成.py --モデル qwen2.5-coder:14b --型 10 --件 18 --出し先 事例/D3-対照-qwen25.jsonl >>$記 2>&1

言 "gemma4 を常駐に戻して印を外す"
python3 -c "
import json,urllib.request
urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:11434/api/chat',
 data=json.dumps({'model':'gemma4:26b','messages':[{'role':'user','content':'hi'}],
 'stream':False,'keep_alive':-1}).encode(),
 headers={'Content-Type':'application/json'}), timeout=600)
print('gemma4 を常駐に戻した')" | tee -a $記
python3 -c "
import sys,os; sys.path.insert(0,os.path.expanduser('~/bin'))
from guardlib import maintenance_clear, maintenance
maintenance_clear(); print('印を外した:', maintenance())" | tee -a $記
言 "== 追検証おわり =="
