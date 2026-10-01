#!/bin/zsh
# 総比較 — 総検証で作った全アームに、全部の門を当てて並べる。
set -u
cd ~/評価層
出=記録/総比較-$(date +%Y%m%d-%H%M%S).txt
表(){ echo; echo "########## $1"; shift; node 門の比較.mjs "$@" 2>&1 | tail -12 }
{
  echo "総比較 $(date '+%Y-%m-%d %H:%M')"
  表 "① gemma4 の素（型1-3・6本）" 事例/20260922-234732.jsonl 事例/20260923-004516.jsonl \
     事例/20260923-021044.jsonl 事例/20260923-033700.jsonl 事例/20260923-053355.jsonl 事例/20260923-065323.jsonl
  [ -f 事例/A1-対照-gemma4.jsonl ]      && 表 "② 対照・調べただけ（gemma4）"        事例/A1-対照-gemma4.jsonl
  [ -f 事例/A2-言い換え-gemma4.jsonl ]  && 表 "③ 言い換え（gemma4 が書いた）"        事例/A2-言い換え-gemma4.jsonl
  [ -f 事例/A3-語伏せ-gemma4.jsonl ]    && 表 "④ 指示の語を伏せた（gemma4）"          事例/A3-語伏せ-gemma4.jsonl
  [ -f 事例/B1-束-qwen3.jsonl ]         && 表 "⑤ 別モデルの束（qwen3:14b）"          事例/B1-束-qwen3.jsonl
  [ -f 事例/B2-対照-qwen3.jsonl ]       && 表 "⑥ 対照・調べただけ（qwen3）"          事例/B2-対照-qwen3.jsonl
  [ -f 事例/B3-言い換え-qwen3.jsonl ]   && 表 "⑦ 言い換え（qwen3 が書いた）"         事例/B3-言い換え-qwen3.jsonl
  [ -f 事例/C1-束-qwen25coder.jsonl ]   && 表 "⑧ 別モデルの束（qwen2.5-coder:14b）"  事例/C1-束-qwen25coder.jsonl
  [ -f 事例/C2-対照-qwen25coder.jsonl ] && 表 "⑨ 対照・調べただけ（qwen2.5-coder）"  事例/C2-対照-qwen25coder.jsonl
  echo; echo "########## ⑩ 全部まとめて"
  node 門の比較.mjs 事例/*.jsonl 2>&1 | tail -12
} | tee $出
echo "→ $出"
