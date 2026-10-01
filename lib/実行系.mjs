// 事例を、本物の qwc の道具で、砂場に対して実際に走らせる。
//
// ■ なぜ本物の道具を使うか
//   道具の真似を書くと、**真似のほうが正しくなる**。
//   実機で起きた嘘の多くは「道具が断った」「道具の中で失敗した」ところから生まれている。
//   断り方や失敗の数え方を写し取った瞬間に、写し損ねた分だけ評価が甘くなる。
//   qwc の tools.mjs をそのまま呼べば、写す物が無い。
//
// ■ ここで作る ctx は agent.mjs と同じ形でなければならない
//   見張り（agent.mjs の promptIfNoWork 相当）は ctx の中身しか見ない。
//   1つでも欠けると、見張りは鳴らないのではなく**静かに素通りする**。
//   だから agent.mjs:72 の初期化と、facts.mjs の先渡しと、
//   agent.mjs:1184 の noteWriteBlocked を、ここで揃えて再現する。
import fs from 'node:fs';
import path from 'node:path';

const QWC = process.env.QWC_SRC || path.join(process.env.HOME, 'コーディングCLI', 'src');

const { DEFAULT_CONFIG } = await import(path.join(QWC, 'config.mjs'));
const { TOOL_MAP } = await import(path.join(QWC, 'tools.mjs'));
const { beginTurn } = await import(path.join(QWC, 'edits.mjs'));
const facts = await import(path.join(QWC, 'facts.mjs'));
const { 門を通す } = await import(new URL('./門.mjs', import.meta.url));

/** 砂場の中身をぜんぶ読む。神託（真偽.mjs）が世界の前後を比べるために使う。 */
export function 写す(root) {
  const out = new Map();
  const 歩く = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) 歩く(p);
      else if (e.isFile()) {
        const rel = path.relative(root, p);
        try {
          out.set(rel, fs.readFileSync(p, 'utf8'));
        } catch {
          out.set(rel, null); // 読めないもの（＝比べられない）は null で残す。無かったことにしない
        }
      }
    }
  };
  if (fs.existsSync(root)) 歩く(root);
  return out;
}

/** agent.mjs:72 と同じ形の ctx。欠けると見張りが静かに素通りするので、多めに持つ側に倒す。 */
function ctxを組む(root) {
  const config = { ...DEFAULT_CONFIG, commandTimeoutMs: 20000 };
  return {
    root,
    config,
    permissions: { allows: () => true },
    changedFiles: new Set(),
    readFiles: new Set(),
    editFailures: new Map(),
    writeOk: new Map(),
    writeFail: new Map(),
    // tools.mjs:495 countCommand が入れる。門で止めたぶんも、ここに同じ形で入れる
    cmdOk: new Map(),
    cmdFail: new Map(),
    mutations: 0,
    todos: [],
    editLog: [],
    editBaseline: new Map(),
    editDropped: new Map(),
    turnSeq: 0,
    signal: null,
    missingKnown: [],
    missingFromRequest: []
  };
}

/**
 * 依頼から「この作業場に無いと分かっている名前」を先に出す（facts.mjs をそのまま呼ぶ）。
 *
 * agent.mjs:219〜246 と同じ順で呼ぶ。ここを自分で書くと、
 * 型3（存在しないものの辻褄合わせ）の見張りが、評価の中だけ賢くなる。
 */
function 事実を先渡し(依頼, ctx) {
  // **agent.mjs と同じ門を立てる。** ここを落としていたせいで、
  // 評価層の判定が本番と違うものを測っていた（2026-09-24 に実地で発覚）。
  // 本番は runTurn の頭で ctx.requestIsQuestion を立て、上の門として使う。
  ctx.requestIsQuestion = facts.requestIsQuestion ? facts.requestIsQuestion(依頼) : false;
  // 本番（agent.mjs）と同じものを持たせる。片方に無いと、
  // 評価層で直したつもりのものが本番で効かない（2026-09-25 に踏んだ）。
  ctx.requestText = String(依頼 ?? "");
  const names = facts.namesInRequest(依頼);
  const paths = facts.pathsInRequest(依頼);
  if (!names.length && !paths.length) return;
  const 名前の欠け = names.length ? facts.missingNames(names, ctx) : [];
  const パスの欠け = paths.length ? facts.missingPaths(paths, ctx) : [];
  const missing =
    名前の欠け === null || パスの欠け === null ? null : [...名前の欠け, ...パスの欠け];
  if (missing && facts.treatsAsExisting(依頼)) {
    ctx.missingFromRequest = missing;
    ctx.missingKnown = missing;
  }
}

/**
 * 道具に届く前に断られた書き換えを、失敗として数える（agent.mjs:1184 と同じ）。
 *
 * 道具の中で失敗したものは tools.mjs が数えている。**断られたものはどこにも残らない。**
 * 実機 2026-09-10 で、断られた write_file について「書き換えました」と報告し、
 * どの見張りも鳴らなかった。ここを落とすと、その穴が評価からも消える。
 */
function 断られたのを数える(tool, args, ctx, root) {
  if (!tool || (tool.name !== 'edit_file' && tool.name !== 'write_file')) return;
  const raw = args && args.path;
  if (!raw) return;
  let abs;
  try {
    abs = path.resolve(root, String(raw));
  } catch {
    return;
  }
  ctx.writeFail.set(abs, (ctx.writeFail.get(abs) || 0) + 1);
}

/**
 * 1事例を走らせる。
 *
 * 返すのは「起きたこと」だけで、**良し悪しは一切含めない**。
 * 良し悪しは神託（真偽.mjs）と見張り（検知.mjs）が別々に付ける。
 * ここで少しでも判定を混ぜると、両方が同じ勘違いを共有することになる。
 */
export async function 走らせる(事例, root) {
  fs.mkdirSync(root, { recursive: true });
  for (const [rel, body] of Object.entries(事例.作業場 || {})) {
    const p = path.join(root, rel);
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(p, String(body), 'utf8');
  }

  const 前 = 写す(root);
  const ctx = ctxを組む(root);
  事実を先渡し(String(事例.依頼 || ''), ctx);

  // agent.mjs:255〜262 と同じ順。書き換えの成否は「そのお願いの中」で見る
  beginTurn(ctx);
  ctx.writeOk.clear();
  ctx.writeFail.clear();
  // **qwc 本体はここで cmdOk / cmdFail を消していない**（agent.mjs:260 は writeOk/writeFail だけ）。
  // 前の依頼で失敗したコマンドが残るので、次の依頼の報告にも「触れていない」が鳴りうる。
  // 1事例＝1依頼のここでは違いが出ないので消しているが、**本体の挙動とは違う**。
  // 持ち越しが実際に鳴るかは別に測ること（README「見つけたが直していないもの」）。
  ctx.cmdOk.clear();
  ctx.cmdFail.clear();

  const messages = [];
  const 手の結果 = [];
  for (const 手 of 事例.手 || []) {
    const tool = TOOL_MAP.get(手.道具);
    if (!tool) {
      手の結果.push({ ...手, 断られた: true, 出力: `そんな道具は無い: ${手.道具}` });
      continue;
    }
    const args = 手.引数 || {};
    let 結果;
    // 門で止めたものは「無かったこと」にせず、**通らなかったコマンド**として残す。
    // 握りつぶすと、型1の半分（コマンドで世界を変えたという嘘）が測れなくなる。
    const 門 = 門を通す(手);
    if (門) {
      ctx.cmdFail.set(String(args.command || '').trim(), (ctx.cmdFail.get(String(args.command || '').trim()) || 0) + 1);
      ctx.mutations = (ctx.mutations || 0) + 1;
      const content = `Exit code: 126\n\n${門}`;
      messages.push({ role: 'tool', tool_name: 手.道具, turn: ctx.turnSeq, content });
      手の結果.push({ 道具: 手.道具, 引数: args, isError: true, 出力: content, 門で止めた: true });
      continue;
    }
    try {
      const ng = tool.validate ? tool.validate(args, ctx) : null;
      if (ng) {
        断られたのを数える(tool, args, ctx, root);
        結果 = { isError: true, output: String(ng) };
      } else {
        結果 = await tool.run(args, ctx);
      }
    } catch (err) {
      // 道具が投げた場合も、断られたのと同じ「何も書けていない」である
      断られたのを数える(tool, args, ctx, root);
      結果 = { isError: true, output: `${err.name}: ${err.message}` };
    }
    const content = String(結果.output ?? '');
    messages.push({ role: 'tool', tool_name: 手.道具, turn: ctx.turnSeq, content });
    手の結果.push({ 道具: 手.道具, 引数: args, isError: Boolean(結果.isError), 出力: content });
  }

  return { ctx, messages, 前, 後: 写す(root), 手の結果, turn: ctx.turnSeq };
}
