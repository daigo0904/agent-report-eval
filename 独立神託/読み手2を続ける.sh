#!/bin/sh
# 実走の読み手が終わったら、間を空けずに held-out の読み手を再開する（daigo-b4 の一晩の計測に割り込まないため）
cd "$(dirname "$0")"
while pgrep -f "読み手2.py 実走" > /dev/null; do sleep 10; done
python3 読み手2.py 1 2 3 4 AI > 読み手2.log 2>&1
echo "held-out の読み手 終わり: $(wc -l < 出力-gemma4.jsonl) 件"
