// 本物の会話の記録に、qwc の見張りを「全部」当てる（2026-09-27・daigo-de）
//
//   node 全部当てる.mjs <qwc の src のパス> <実走-XXXX.jsonl> <出力.jsonl>   （qwc の画面表示は標準出力に出るので、結果はファイルに書く）
//
// やり方: 本物の qwc の Agent.runTurn をそのまま動かす。
//   - モデルの発言      … 本物の会話の assistant の発言を順に返す
//   - ファイルの道具    … 一時フォルダ（課題の最初のファイル）で本当に動かす（結果は本物と同じはず）
//   - run_command       … **走らせない。**本物の会話に残った結果を返し、qwc と同じ決まりで帳簿（cmdOk/cmdFail/mutations）に付ける
//                         （評価層の再生は門がコマンドを止めて成否が183中35件で化けた。その穴をここで塞ぐ）
//   - ずれの検知       … ファイルの道具の出力が本物と違ったら、その回から先を「ずれた」として印を付ける
//                         （コマンドが作ったファイルを読む、など）。ずれた後の報告は集計から外す
// 促しは runTurn が自分で差し込む。差し込まれた文を拾って、本物の促しと並べる。
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const [SRC, 入力, 出先] = process.argv.slice(2);
const 書く = (x) => fs.appendFileSync(出先, JSON.stringify(x) + '\n');
fs.writeFileSync(出先, '');
const { Agent } = await import(path.join(SRC, 'agent.mjs'));
const { DEFAULT_CONFIG } = await import(path.join(SRC, 'config.mjs'));
const { PermissionManager } = await import(path.join(SRC, 'permissions.mjs'));

const 中身を見ない = /todo_write|taking several steps|Stop reading|changed nothing yet/i;
// 作業フォルダの名前（本物は /Users/Shared/実走-XX-…、再現は一時フォルダ）は伏せる。検索の結果は並び順を揃える
const 正規化 = (s, root) => String(s ?? '')
  .split(root ?? '\u0000').join('<作業場>')
  .replace(/\/Users\/Shared\/実走-[^\s)"'`/]*/g, '<作業場>')
  .split('\n').map((x) => x.trimEnd()).sort().join('\n').trim();

class 会話を演じる extends Agent {
  constructor(opts, 発言, 結果の列) {
    super(opts);
    this.発言 = 発言;              // assistant の発言（本物の順）
    this.番 = 0;
    this.結果の列 = 結果の列;      // 道具の呼び出しの本物の結果（本物の順）
    this.道具番 = 0;
    this.ずれ = null;
    this.報告 = [];                // {報告, 促し文}
  }
  async streamAssistant() {
    // 直前が促し（runTurn が差し込んだ user 発言）なら、1つ前の報告に付ける
    const 直前 = this.messages[this.messages.length - 1];
    if (this.報告.length && 直前?.role === 'user' && this.報告[this.報告.length - 1].促し文 === undefined) {
      this.報告[this.報告.length - 1].促し文 = String(直前.content);
    }
    const m = this.発言[this.番++];
    if (!m) return { message: { role: 'assistant', content: '' }, toolCalls: [], stats: null };
    const calls = (m.tool_calls || []).map((c, k) => ({
      name: c.function?.name, args: typeof c.function?.arguments === 'string' ? JSON.parse(c.function.arguments) : (c.function?.arguments || {}),
      id: c.id || `t${this.番}-${k}`
    }));
    if (!calls.length && String(m.content || '').trim()) this.報告.push({ 報告: m.content, ずれた後: !!this.ずれ, 促し文: undefined });
    return { message: { role: 'assistant', content: m.content || '' }, toolCalls: calls, stats: null };
  }
  async executeTool(call, ...rest) {
    const 本物 = this.結果の列[this.道具番++];
    if (call.name === 'run_command') {
      const cmd = String(call.args?.command ?? '').trim();
      const out = String(本物?.content ?? '');
      const code = Number((out.match(/Exit code:\s*(-?\d+)/) || [])[1] ?? NaN);
      const 時間切れ = /timed out|タイムアウト/i.test(out.slice(0, 200));
      const 答えが無いだけ = code === 1 && /^(?:grep|rg|egrep|fgrep|find|fd|diff|ls|test|\[)\b/.test(cmd);
      this.ctx.mutations = (this.ctx.mutations || 0) + 1;
      const key = !時間切れ && (code === 0 || 答えが無いだけ) ? 'cmdOk' : 'cmdFail';
      if (!(this.ctx[key] instanceof Map)) this.ctx[key] = new Map();
      if (cmd) this.ctx[key].set(cmd, (this.ctx[key].get(cmd) || 0) + 1);
      return { output: out, denied: false };
    }
    const r = await super.executeTool(call, ...rest);
    if (!this.ずれ && 本物 && 正規化(r?.output, this.root) !== 正規化(本物.content)) {
      this.ずれ = { 道具: call.name, 番: this.道具番, 再現: String(r?.output).slice(0, 120), 本物: String(本物.content).slice(0, 120) };
    }
    return r;
  }
}

for (const 行 of fs.readFileSync(入力, 'utf8').split('\n')) {
  if (!行.trim()) continue;
  const r = JSON.parse(行);
  if (!r.会話 || r.課題 === 'D3') continue;
  const root = fs.mkdtempSync(path.join(os.tmpdir(), '全部当てる-'));
  try {
    for (const [名, 中身] of Object.entries(r.最初の作業場 || {})) {
      if (中身 == null) continue;
      const p = path.join(root, 名);
      fs.mkdirSync(path.dirname(p), { recursive: true });
      fs.writeFileSync(p, 中身, 'utf8');
      if (名.endsWith('.sh')) fs.chmodSync(p, 0o755);
    }
    const msgs = r.会話;
    const 発言 = msgs.filter((m) => m.role === 'assistant');
    const 結果 = new Map(msgs.filter((m) => m.role === 'tool').map((m) => [m.tool_call_id, m]));
    const 結果の列 = 発言.flatMap((m) => (m.tool_calls || []).map((c) => 結果.get(c.id)));
    // 本物の促し: 各報告の直後の user 発言
    const 本物の促し = [];
    msgs.forEach((m, j) => {
      if (m.role !== 'assistant' || (m.tool_calls || []).length || !String(m.content || '').trim()) return;
      const 次 = msgs.slice(j + 1).find((y) => y.role === 'user' || y.role === 'assistant');
      本物の促し.push(次 && 次.role === 'user' ? String(次.content) : null);
    });
    const cfg = { ...DEFAULT_CONFIG, autoApprove: true, commandTimeoutMs: 20000 };
    const a = new 会話を演じる({ config: cfg, root, permissions: new PermissionManager(cfg, async () => 'y') }, 発言, 結果の列);
    const 頼み = String(msgs.find((m) => m.role === 'user')?.content ?? r.頼み);
    try { await a.runTurn(頼み); } catch (e) { a.例外 = String(e?.message ?? e); }
    a.報告.forEach((x, k) => {
      const 促し = x.促し文 ?? null;
      const 本 = 本物の促し[k] ?? null;
      書く({
        id: `実走-${r.課題}-${r.回}-${k + 1}`, 課題: r.課題, 回: r.回, 何番目: k + 1,
        ずれた後: x.ずれた後,
        鳴った: !!促し && !中身を見ない.test(促し), 促し: 促し ? 促し.slice(0, 160) : null,
        本物で鳴った: !!本 && !中身を見ない.test(本), 本物の促し: 本 ? 本.slice(0, 160) : null
      });
    });
    if (a.ずれ || a.例外) process.stderr.write(`${r.課題}-${r.回}: ずれ=${JSON.stringify(a.ずれ)} 例外=${a.例外 ?? ''}\n`);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}
