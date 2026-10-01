#!/usr/bin/env node
// 確かめ — 前の依頼で失敗したコマンドが、次の依頼の報告にも「触れていない」と鳴るか。
//
// ■ なぜ確かめるか
//   agent.mjs:258 にこう書いてある。
//     「書き換えの成否は**そのお願いの中**で見る。前の依頼の失敗を持ち越すと、
//       今回きちんと直した報告まで嘘だと言うことになる。」
//   そう書いてあって、消しているのは writeOk / writeFail だけで、
//   **cmdOk / cmdFail は消していない**（grep しても他に出てこない）。
//   理由が正しいなら、コマンドにも同じことが起きるはずである。当ててみる。
//
// ■ ここで測れること／測れないこと
//   測れる … agent.mjs が依頼と依頼のあいだにやることを同じ順で再現したとき、
//            commandsNeverRan が前の依頼の失敗を返し続けるか（コードの経路）
//   測れない … 実機の会話でこれが実際に促しを出したか（モデルを回していない）
import path from 'node:path';
const QWC = process.env.QWC_SRC || path.join(process.env.HOME, 'コーディングCLI', 'src');
const A = await import(path.join(QWC, 'agent.mjs'));
const { beginTurn } = await import(path.join(QWC, 'edits.mjs'));

const ctx = {
  writeOk: new Map(), writeFail: new Map(),
  cmdOk: new Map(), cmdFail: new Map(),
  editLog: [], editBaseline: new Map(), editDropped: new Map(), turnSeq: 0
};

// ── 1回目のお願い：sudo が通らなかった（tools.mjs:1038 countCommand と同じ形で入れる）
beginTurn(ctx);
ctx.cmdFail.set('sudo launchctl kickstart -k gui/501/x', 1);
ctx.writeFail.set('/tmp/a.py', 1);
console.log('  1回目のあと  通らなかったコマンド:', A.commandsNeverRan(ctx));
console.log('               通らなかった書き換え:', A.filesNeverWritten(ctx));

// ── 2回目のお願いが始まる（agent.mjs:255〜261 と同じ順・同じ範囲）
beginTurn(ctx);
ctx.writeOk.clear();
ctx.writeFail.clear();
// ここに cmdOk.clear() / cmdFail.clear() は無い。agent.mjs にも無い

const 報告 = 'app.py のインデントを直しました。';
const 残り = A.commandsNeverRan(ctx);
const 鳴る = A.unmentionedCommands(報告, 残り);
console.log('  2回目のあと  通らなかったコマンド:', 残り);
console.log('               通らなかった書き換え:', A.filesNeverWritten(ctx));
console.log(`\n  2回目の報告「${報告}」に対して`);
console.log('  →', 鳴る.length ? `鳴る（${鳴る[0]}）：前の依頼の失敗を持ち越している` : '鳴らない');
console.log(鳴る.length
  ? '\n  書き換えのほうは消えている。コマンドのほうだけ残る。**左右が揃っていない。**'
  : '\n  持ち越していない。');
