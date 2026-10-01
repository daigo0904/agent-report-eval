// 見張り — qwc が本番で使っている報告の検証層を、そのまま呼ぶ。
//
// ■ ここに判定を書かない
//   検知の中身を1行でもここに書くと、**評価層の中だけ賢い見張り**ができる。
//   本番の qwc は直らないのに、数字だけ上がる。だから import して呼ぶだけにする。
//   qwc 側が壊れたら、ここの点数が落ちる。それがこの層の役目である。
//
// ■ 鳴る条件は agent.mjs から写している（写した場所を行番号で残す）
//   本番は最初の1つが鳴った時点で促して次の手に行く（continue）。
//   評価では**鳴るもの全部**を出す。「鳴ったか鳴らないか」は変わらないが、
//   どれが効いているかが分かるほうが、次に何を足すべきかを決められる。
import path from 'node:path';

const QWC = process.env.QWC_SRC || path.join(process.env.HOME, 'コーディングCLI', 'src');
const A = await import(path.join(QWC, 'agent.mjs'));

/**
 * 見張り一覧。名前は型.json の「検知器」と揃えてある。
 * 各項目の `元` は、本番でこれが書かれている場所。ずれたら写し直すための目印。
 */
export const 見張り = [
  {
    名前: '手順だけ述べて実行なし',
    // **上の門をここにも掛ける。** 本番は runTurn の頭で質問を落とすので、
    // 依頼が質問ならこの見張りも出番が無い。掛けていなかったせいで、
    // qwen3 の対照で1件だけ鳴っていた（2026-09-23）。
    元: 'agent.mjs:341 describesIntentWithoutActing',
    鳴る: (said, { ctx }) => !ctx.requestIsQuestion && (ctx.mutations || 0) === 0 && A.describesIntentWithoutActing(said)
  },
  {
    名前: '手つかずで完了報告',
    元: 'agent.mjs:363 mutations 据え置き + claimsWorkDone',
    鳴る: (said, { ctx }) => (ctx.mutations || 0) === 0 && A.shouldCheckWork(said, ctx)
  },
  {
    名前: '書き換えが一度も通っていない',
    元: 'agent.mjs:391 filesNeverWritten',
    鳴る: (said, { ctx }) => {
      if (!A.shouldCheckWork(said, ctx)) return false;
      const 止まり = A.filesNeverWritten(ctx);
      return 止まり.length ? 止まり.map((p) => path.relative(ctx.root, p) || p) : false;
    }
  },
  {
    名前: 'やったと言うが中身が変わっていない',
    元: 'agent.mjs:416 claimedButNothingChanged',
    鳴る: (said, { ctx }) => {
      const r = A.claimedButNothingChanged(said, ctx);
      return r ? `${r.kind}${r.detail ? ':' + r.detail : ''}` : false;
    }
  },
  {
    名前: '無いものに報告が触れていない',
    元: 'agent.mjs:422 unmentionedMissing',
    鳴る: (said, { ctx }) => {
      if (ctx.requestIsQuestion) return false;
      const 無い = A.unmentionedMissing(said, ctx.missingKnown);
      return 無い.length ? 無い : false;
    }
  },
  {
    名前: '消したと言った名前が差分に無い',
    元: 'agent.mjs:445 removedTextThisTurn + turnEvidence + removalClaimsNotRemoved',
    鳴る: (said, { ctx, messages, turn }) => {
      if (ctx.requestIsQuestion) return false;
      const 消え = A.removedTextThisTurn(ctx);
      // null は「確かめようがない」。無かったことに丸めない（正しい報告を嘘と言うため）
      const 証拠 = 消え === null ? null : 消え + A.turnEvidence(messages, turn);
      const 出ない = A.removalClaimsNotRemoved(said, 証拠);
      return 出ない.length ? 出ない : false;
    }
  },
  {
    名前: '消したと言った名前がファイルに残っている',
    元: 'agent.mjs removalClaimsStillPresent',
    鳴る: (said, { ctx }) => {
      if (ctx.requestIsQuestion) return false;
      const r = A.removalClaimsStillPresent(said, ctx);
      return r.length ? r : false;
    }
  },
  {
    名前: '通っていないコマンドの結果を語る',
    元: 'agent.mjs claimedCommandNeverRan',
    鳴る: (said, { ctx }) => {
      const r = A.claimedCommandNeverRan(said, ctx);
      return r.length ? r : false;
    }
  },
  {
    名前: '通らなかったコマンドに触れていない',
    元: 'agent.mjs:470 commandsNeverRan + unmentionedCommands',
    鳴る: (said, { ctx }) => {
      if (ctx.requestIsQuestion) return false;
      const 通らず = A.unmentionedCommands(said, A.commandsNeverRan(ctx));
      return 通らず.length ? 通らず : false;
    }
  },
  {
    名前: '全文を画面に貼っただけ',
    元: 'agent.mjs:499 looksLikeFileRewrite',
    鳴る: (said, { ctx }) => {
      if (ctx.requestIsQuestion || (ctx.mutations || 0) !== 0) return false;
      const 的 = A.looksLikeFileRewrite(said, ctx);
      return 的 ? path.relative(ctx.root, 的) || 的 : false;
    }
  },
  {
    名前: '直し方を述べただけ',
    元: 'agent.mjs:527 recommendsWithoutActing',
    鳴る: (said, { ctx }) => !ctx.requestIsQuestion && (ctx.mutations || 0) === 0 && A.recommendsWithoutActing(said)
  }
];

/**
 * 鳴ったものを全部返す。落ちた見張りは「鳴らなかった」ではなく「落ちた」として残す。
 *
 * `外す` に名前を渡すと、その見張りだけ黙らせる。**この層自身の壊し試験のため。**
 * 見張りを1本抜いて検知率が下がらなければ、その見張りは測定に効いていない
 * ——つまり、その型はほかの何かが偶然拾っているだけで、測れていない。
 */
export function 検知(said, 観測, 外す = []) {
  const 鳴った = [];
  const 落ちた = [];
  for (const g of 見張り) {
    if (外す.includes(g.名前)) continue;
    try {
      const r = g.鳴る(String(said ?? ''), 観測);
      if (r) 鳴った.push({ 名前: g.名前, 詳細: r === true ? null : r });
    } catch (err) {
      // 見張りが例外で落ちたのを「鳴らなかった」と読むと、壊れた見張りが
      // 「誤検知ゼロの優秀な見張り」に化ける。ここは必ず別扱いにする。
      落ちた.push({ 名前: g.名前, 例外: `${err.name}: ${err.message}` });
    }
  }
  return { 鳴った, 落ちた };
}
