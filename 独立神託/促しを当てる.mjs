// 本物の会話の報告に、指定した版の claimedRunningSomethingNeverRun を直に当てる（ollama も再生も使わない）
import fs from 'node:fs';
const 版 = process.argv[2];
const A = await import(`/private/tmp/claude-501/-Users-daigo/692ff985-c691-4d7b-9385-d1725a4b97cd/scratchpad/qwc-${版}/src/agent.mjs`);
let 本番で鳴った = 0, 再現 = 0, 鳴った = 0, 全 = 0, 対象 = 0;
for (const l of fs.readFileSync('実走-20260926-1159.jsonl', 'utf8').split('\n')) {
  if (!l.trim()) continue;
  const r = JSON.parse(l);
  if (!r.会話) continue;
  const m = r.会話, 結果 = new Map(m.filter((x) => x.role === 'tool').map((x) => [x.tool_call_id, String(x.content)]));
  const cmdOk = new Map(), cmdFail = new Map();
  m.forEach((x, j) => {
    if (x.role !== 'assistant') return;
    for (const c of x.tool_calls || []) {
      if (c.function.name !== 'run_command') continue;
      const cmd = String(c.function.arguments?.command ?? '').trim();
      const ok = /^Exit code:\s*0\b/.test(結果.get(c.id) ?? '');
      (ok ? cmdOk : cmdFail).set(cmd, ((ok ? cmdOk : cmdFail).get(cmd) || 0) + 1);
    }
    if ((x.tool_calls || []).length || !String(x.content || '').trim()) return;
    全++;
    const 次 = m.slice(j + 1).find((y) => y.role === 'user' || y.role === 'assistant');
    const 本番 = !!(次 && 次.role === 'user' && /You said you executed something/.test(次.content));
    const 今 = A.claimedRunningSomethingNeverRun(x.content, { requestIsQuestion: false, cmdOk, cmdFail }).length > 0;
    本番で鳴った += 本番; 鳴った += 今; if (本番 && 今) 再現++;
    if (今 && process.argv[3]) { const 書いた = [...String(x.content).matchAll(/`([^`\n]+)`/g)].map((q) => q[1].trim()); console.log(`  鳴った ${r.課題}-${r.回}: 逐語で走った=${書いた.some((s) => cmdOk.has(s) || cmdFail.has(s))} 走った=[${[...cmdOk.keys(), ...cmdFail.keys()].join(" | ").slice(0,90)}] 報告=${String(x.content).slice(0, 140).replace(/\n/g, " ")}`); }
  });
}
console.log(`${版}: 報告 ${全}・本番で「実行したと言うが走っていない」が出た ${本番で鳴った}・この版を当てて鳴る ${鳴った}（うち本番と重なる ${再現}）`);
