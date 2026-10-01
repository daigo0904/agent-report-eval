#!/bin/sh
cd "$(dirname "$0")"
for k in 1 2 3; do
  sed "s/FILE/束-実走$k.txt/" 頼み.txt > p-実走$k.txt
  ~/.local/bin/codex exec --skip-git-repo-check -C "$PWD" "$(cat p-実走$k.txt)" < /dev/null > 出力-実走$k.txt 2>&1
  echo "Codex 束$k: $(grep -c '"番号"' 出力-実走$k.txt) 行・上限 $(grep -c 'hit your usage limit' 出力-実走$k.txt)"
done
