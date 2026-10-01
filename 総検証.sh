#!/bin/zsh
# 総検証 — 「どんなモデルでも検知できるか」を、私が選ばない形で測り切る。
#
# ■ 順番に意味がある
#   最初に回すのは型10（調べて答えただけの対照）。反転版はここで壊れる見込みで、
#   壊れているなら他の検知率がいくら良くても採用できない。
#   良い数字を先に見ると判断が濁るので、**先に壊れうるほうを見る**。
#
# ■ モデルの載せ替え
#   ollama は1つしか載らない。載せ替えの間 model-guard が gemma4 を常駐に
#   戻しにくるので、手入れの印を置く（model-guard は stand_down を見る）。
#   印は期限つきなので、この本が落ちても自然に外れる。
set -u
cd ~/評価層
記=記録/総検証-$(date +%Y%m%d-%H%M%S).log
言(){ echo "[$(date +%H:%M:%S)] $*" | tee -a $記 }

言 "== A 相: gemma4 が載っているまま =="
言 "A1 対照（型10・調べて答えただけ）10件"
python3 生成.py --型 10 --件 10 --出し先 事例/A1-対照-gemma4.jsonl >>$記 2>&1

言 "A2 言い換え（gemma4 に書き換えさせる・嘘だけ）"
python3 言い換え.py 事例/20260922-234732.jsonl 事例/20260923-004516.jsonl \
  事例/20260923-021044.jsonl 事例/20260923-033700.jsonl 事例/20260923-053355.jsonl \
  --嘘だけ --出し先 事例/A2-言い換え-gemma4.jsonl >>$記 2>&1

言 "A3 指示の語を伏せた版（型1-3・各4件）"
python3 生成.py --件 4 --語を伏せる --出し先 事例/A3-語伏せ-gemma4.jsonl >>$記 2>&1

言 "== B 相: qwen3:14b に載せ替え =="
python3 -c "
import sys,os; sys.path.insert(0,os.path.expanduser('~/bin'))
from guardlib import maintenance_hold
maintenance_hold('別モデルでの総検証（評価層）', 7200, by='eval-crossmodel')
print('手入れの印を置いた（2時間）')" | tee -a $記

python3 生成.py --モデル qwen3:14b-q4_K_M --件 4 --出し先 事例/B1-束-qwen3.jsonl >>$記 2>&1
python3 生成.py --モデル qwen3:14b-q4_K_M --型 10 --件 6 --出し先 事例/B2-対照-qwen3.jsonl >>$記 2>&1
python3 言い換え.py 事例/20260923-021044.jsonl 事例/20260923-033700.jsonl 事例/20260923-053355.jsonl \
  --モデル qwen3:14b-q4_K_M --嘘だけ --出し先 事例/B3-言い換え-qwen3.jsonl >>$記 2>&1

言 "== C 相: qwen2.5-coder:14b に載せ替え =="
python3 生成.py --モデル qwen2.5-coder:14b --件 4 --出し先 事例/C1-束-qwen25coder.jsonl >>$記 2>&1
python3 生成.py --モデル qwen2.5-coder:14b --型 10 --件 6 --出し先 事例/C2-対照-qwen25coder.jsonl >>$記 2>&1

言 "== D 相: gemma4 を常駐に戻して、印を外す =="
python3 -c "
import json,urllib.request
urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:11434/api/chat',
 data=json.dumps({'model':'gemma4:26b','messages':[{'role':'user','content':'hi'}],
 'stream':False,'keep_alive':-1}).encode(),
 headers={'Content-Type':'application/json'}), timeout=300)
print('gemma4 を常駐に戻した')" | tee -a $記
python3 -c "
import sys,os; sys.path.insert(0,os.path.expanduser('~/bin'))
from guardlib import maintenance_clear, maintenance
maintenance_clear(); print('印を外した:', maintenance())" | tee -a $記

言 "== 生成おわり =="
ls -la 事例/[ABC]*.jsonl | tee -a $記
