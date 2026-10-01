#!/bin/sh
cd "$(dirname "$0")"
for k in ${束:-1 2 3 4 再読}; do
  sed "s/FILE/束-$k.txt/" 頼み.txt > p-$k.txt
  ~/.local/bin/codex exec --skip-git-repo-check -C "$PWD" "$(cat p-$k.txt)" < /dev/null > 出力-$k.txt 2>&1
  echo "束$k: $(grep -c '"番号"' 出力-$k.txt) 行・上限 $(grep -c 'hit your usage limit' 出力-$k.txt)"
done
