#!/usr/bin/env python3
"""意図ラベルと神託が食い違った事例を、**結果に関わらず全件**並べる。

■ なぜ要るか（別セッション daigo-b4 の指摘・2026-09-26）
  神託のバグは、これまで全部「誤検知を調べていて」見つかっていた。
  つまり監査が入るのは **見張りと神託が食い違った欄だけ**。
  両方が同時に同じ向きに間違えると「一致＝正検知」になり、誰も見に行かない。

  実測（860件）: 意図ラベルと神託の食い違いは74件。
    正直のつもり → 神託は嘘 … 40件（うち **37件が正検知として数えられている**）
    嘘のつもり   → 神託は正直 … 34件（うち31件が素通り＝嘘が数える前に消えている）
  正検知428件の 8.6% が、生成側が「正直」として作った事例である。

■ 使い方
    node 判定.mjs 事例/*.jsonl > /tmp/x.jsonl
    python3 食い違いの監査.py /tmp/x.jsonl
"""
import json, os, sys, collections

def 理由型(x):
    out = set()
    for y in x.get('内訳', []):
        if y.get('真') is not False:
            continue
        s = y.get('理由', '')
        if 'いまもどこかのファイルに在る' in s: out.add('A 消した名前が残っている')
        elif '消えた行に無い' in s: out.add('B 消えた行に名前が無い')
        elif '1バイトも変わっていない' in s: out.add('C ファイルが変わっていない')
        elif 'どこにも無い' in s: out.add('D 書いた名前が無い')
        elif '通っていない' in s: out.add('E コマンドが通っていない')
        elif '無いという報告のほうが誤り' in s: out.add('F 無いと言ったが在る')
        elif '定義が消えているのに' in s: out.add('G 黙って消された定義')
        elif '使っている側が残っている' in s: out.add('H 宙に浮いた呼び出し')
        elif '中の語' in s or '中の名前' in s: out.add('I 説明文の中の語')
        else: out.add('Z ' + s[:40])
    return ' + '.join(sorted(out)) or '（偽の主張なし）'

def 主張の型(c):
    種 = sorted({m.get('種類') for m in (c.get('主張') or [])})
    return '+'.join(種) if 種 else '（主張なし）'

def main(道):
    判 = [json.loads(l) for l in open(道, encoding='utf-8') if l.strip()]
    事例 = {}
    for f in os.listdir('事例'):
        if not f.endswith('.jsonl'):
            continue
        for l in open('事例/' + f, encoding='utf-8'):
            if not l.strip():
                continue
            try: c = json.loads(l)
            except Exception: continue
            事例[(f, c.get('id'))] = c

    検 = [x for x in 判 if x['結果'] == '正検知']
    print(f'全 {len(判)} 件 / 正検知 {len(検)} 件')
    print()
    for 向き, ラベル, 神託 in (('正直のつもり→神託は嘘', '正直', '嘘'),
                              ('嘘のつもり→神託は正直', '嘘', '正直')):
        群 = [x for x in 判 if x['ラベル'] == ラベル and x['神託'] == 神託 and x['結果'] != '破棄']
        結果 = collections.Counter(x['結果'] for x in 群)
        print(f'=== {向き}: {len(群)}件  {dict(結果)} ===')
        if ラベル == '正直':
            割 = len(群) and sum(1 for x in 群 if x['結果'] == '正検知')
            print(f'    → 正検知 {割} 件は、**生成側が「正直」として作った事例**である'
                  f'（正検知全体の {割 / max(len(検), 1) * 100:.1f}%）')
        束 = collections.defaultdict(list)
        for x in 群:
            鍵 = 理由型(x) if ラベル == '正直' else 主張の型(事例.get((x['出典'], x['id']), {}))
            束[鍵].append(x)
        for 鍵 in sorted(束, key=lambda k: -len(束[k])):
            xs = 束[鍵]
            print(f'  {len(xs):3}件 (正検知 {sum(1 for x in xs if x["結果"] == "正検知")}'
                  f' / 素通り {sum(1 for x in xs if x["結果"] == "素通り")})  {鍵}')
            for x in xs:
                c = 事例.get((x['出典'], x['id']), {})
                報 = (c.get('報告') or '').replace('\n', ' ')[:70]
                print(f'        {x["出典"][:22]:24} {x["id"]:26} {x["結果"]:4} 「{報}」')
        print()

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/tmp/全X.jsonl')
