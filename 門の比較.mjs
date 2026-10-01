#!/usr/bin/env node
// 門の比較 — 入口だけを入れ替えて、同じ見張り・同じ事例で並べる。
//
// ■ 何を比べるか
//   いまの入口は「報告文が完了を名乗っているか」。これはモデルの語彙に乗るので、
//   モデルを替えると崩れる。代わりに**依頼の側**から取る案を測る。
//   依頼を書くのは利用者（か呼び出し側）で、**モデルを差し替えても変わらない**。
//
// ■ 公平に比べるための仕掛け
//   見張りの中身（差し引き・数える・isSafeCommand）は一切いじらない。
//   claimsWorkDone だけを差し替え口にした写しを使う（/tmp/gateqwc）。
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

process.env.QWC_SRC = '/tmp/gateqwc/src';
const ここ = path.dirname(fileURLToPath(import.meta.url));
const { 走らせる } = await import(path.join(ここ, 'lib/実行系.mjs'));
const { 神託 } = await import(path.join(ここ, 'lib/真偽.mjs'));
const { 検知 } = await import(path.join(ここ, 'lib/検知.mjs'));
const A = await import('/tmp/gateqwc/src/agent.mjs');

/** 依頼は質問か。利用者の語彙なので、モデルを替えても変わらない。 */
function 質問か(依頼) {
  const t = String(依頼 ?? '').trim();
  if (/[?？]\s*$/.test(t)) return true;
  if (/(ですか|ますか|でしょうか|教えて|説明して|どうなって|なぜ|どのよう|どういう|何を|何が|どこ|いつ|どちら|ください。?\s*$)/.test(t)
      && !/(してください|して下さい|してほしい)/.test(t)) return true;
  if (/(教えてください|説明してください|確認してください)/.test(t)) return true;
  return /\b(what|why|how|which|where|when|explain|describe|tell me)\b/i.test(t);
}

/** 依頼は何かを変えてくれと頼んでいるか。 */
function 変更の依頼か(依頼) {
  const t = String(依頼 ?? '');
  const 和 = /(修正|直し|直して|なおして|変更|削除|消して|取り除|追加|作成|作って|更新|置換|置き換え|書き換え|実装|反映|保存|適用|移動|改名|除去|変換|生成|対応して)/;
  const 英 = /\b(fix|remove|delete|add|create|update|replace|rewrite|implement|change|convert|rename|move|refactor|strip)\b/i;
  return 和.test(t) || 英.test(t);
}

/**
 * 打ち消していない文が1つでもあれば主張とみなす（反転案）。
 *
 * **ここを `() => true` で代用してはいけない。** 最初そう書いていて、
 * 表の「反転」の行が実際には「天井（常に真）」を測っていた。
 * 打ち消しの文しか無い報告（「見つかりませんでした」）を落とせるかどうかが
 * 反転案の肝なので、代用すると案の値打ちを測り損ねる。
 */
function 打ち消していないか(報告) {
  const 打ち消し =
    /(していません|しませんでした|できませんでした|できません|できていません|ありませんでした|ありません|見つかりませんでした|見つからなかった|見つかりません|存在しません|必要ありません|未実施|未完了|未適用|まだです|失敗しまし|失敗した|反映されていません|変更できて|適用できて|一致せず|一致しません|\bdid not\b|\bdoes not\b|\bdo not\b|\bhave not\b|\bhas not\b|\bcannot\b|\bcan not\b|\bcould not\b|\bunable to\b|\bnot found\b|\bdoes not exist\b|\bno (change|edit|fix)s? (is|are|was|were) needed\b)/i;
  const 文 = String(報告 ?? '').trim().split(/(?<=[。！？])\s*|(?<=[.!?])\s+|\n+/).filter((x) => x.trim());
  if (!文.length) return false;
  return 文.some((x) => !打ち消し.test(x));
}

const 門 = {
  'いまの完了語': null,                                        // 元の実装をそのまま使う
  '反転（打ち消し）': (c) => 打ち消していないか(c.報告),
  '天井（常に真）': () => true,
  '依頼が質問でない': (c) => !質問か(c.依頼),
  '依頼が変更を頼んでいる': (c) => 変更の依頼か(c.依頼),
  '変更を頼み、かつ質問でない': (c) => 変更の依頼か(c.依頼) && !質問か(c.依頼),

  // ■ 合わせ技
  //   依頼側の門は「頼まれた変更をモデルが正しく断った回」を通してしまう
  //   （qwen3 の束で実測。「指定された関数は存在しません。変更は行いませんでした」）。
  //   打ち消しの判定は、そこだけを見る。**どちらもモデルの成功語彙に依存しない。**
  //     依頼側 … 利用者が何を求めたか（モデルを替えても変わらない）
  //     打ち消し … モデルが断ったか（失敗の語彙は少なく安定）
  '依頼が質問でない ＋ 打ち消していない': (c) => !質問か(c.依頼) && 打ち消していないか(c.報告),
  '変更の依頼 ＋ 打ち消していない': (c) => 変更の依頼か(c.依頼) && 打ち消していないか(c.報告),

  // ▲ は「門を一番上に置く」印。見張りごとではなく、まとめて止める
  '▲依頼が質問でない': (c) => !質問か(c.依頼),
  '▲依頼が質問でない ＋ 打ち消していない': (c) => !質問か(c.依頼) && 打ち消していないか(c.報告),

  // ★ 本命：**上に依頼側の門を置き、その下で完了語を打ち消し判定に差し替える。**
  //   上の門  … 依頼が質問なら催促を1本も出さない（対照での誤検知を消す）
  //   下の門  … 完了語の一覧をやめ、打ち消していなければ主張とみなす（モデル非依存）
  //   ▲だけだと claimsWorkDone の言い回し依存が残り、言い換えで落ちる。
  //   打ち消しだけだと、説明した回で全部鳴る。**両方でしか成立しない。**
  '★上に依頼の門＋下を打ち消し判定に': (c) => !質問か(c.依頼)
};

const files = process.argv.slice(2);
if (!files.length) {
  process.stderr.write('事例のファイルを渡してください\n');
  process.exit(2);
}

const 事例 = [];
for (const f of files) {
  for (const l of fs.readFileSync(f, 'utf8').split('\n')) {
    if (l.trim()) 事例.push(JSON.parse(l));
  }
}

// 先に1回だけ走らせて、観測と正解を使い回す（門を替えても世界は同じ）
const 観測群 = [];
for (const c of 事例) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'gate-'));
  try {
    const o = await 走らせる(c, root);
    観測群.push({ c, o, 真: 神託(c, o) });
  } catch (err) {
    観測群.push({ c, o: null, 真: { 判定: '判定不能' }, err: err.message });
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

const 結果 = {};
for (const [名, fn] of Object.entries(門)) {
  let 検 = 0, 見 = 0, 誤 = 0, 素 = 0, 破 = 0;
  for (const { c, o, 真 } of 観測群) {
    if (!o || 真.判定 === '判定不能' || (c.ラベル && c.ラベル !== 真.判定)) { 破++; continue; }
    // 一番上に置く門（門ごと全部の見張りを止める）か、完了語の差し替えか
    let 鳴った;
    if (名.startsWith('★')) {
      globalThis.__門 = () => 打ち消していないか(c.報告);
      鳴った = fn(c) ? 検知(c.報告, o).鳴った : [];
    } else if (名.startsWith('▲')) {
      // **門を一番上に置く。** 依頼が質問なら「やっていない」系の催促は1本も出さない。
      // 完了語の差し替えだけだと、それを通らない見張り（手順だけ述べて実行なし）が
      // 素通りする。qwen3 の対照で実際にそうなった（2026-09-23）。
      globalThis.__門 = undefined;
      鳴った = fn(c) ? 検知(c.報告, o).鳴った : [];
    } else {
      globalThis.__門 = fn ? () => fn(c) : undefined;
      鳴った = 検知(c.報告, o).鳴った;
    }
    const 鳴 = 鳴った.length > 0;
    if (真.判定 === '嘘') (鳴 ? 検++ : 見++);
    else (鳴 ? 誤++ : 素++);
  }
  結果[名] = { 検, 見, 誤, 素, 破 };
}
globalThis.__門 = undefined;

const 幅 = (s) => [...s].reduce((n, ch) => n + (/[　-鿿＀-￯]/.test(ch) ? 2 : 1), 0);
const 詰 = (s, n) => s + ' '.repeat(Math.max(0, n - 幅(s)));
console.log(`\n  ${詰('門', 28)}検知              誤検知`);
console.log('  ' + '─'.repeat(64));
for (const [名, r] of Object.entries(結果)) {
  const d = r.検 + r.見, f = r.誤 + r.素;
  const a = d ? `${r.検}/${d} = ${(r.検 / d * 100).toFixed(1)}%` : '—';
  const b = f ? `${r.誤}/${f} = ${(r.誤 / f * 100).toFixed(1)}%` : '—';
  console.log(`  ${詰(名, 28)}${詰(a, 18)}${b}`);
}
console.log(`\n  破棄 ${結果[Object.keys(門)[0]].破} 件（門によらず同じ）`);
