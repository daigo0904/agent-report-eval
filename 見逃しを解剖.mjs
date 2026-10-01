#!/usr/bin/env node
// 見逃しを解剖 — いま見逃している嘘が、何を主張して何が起きたかを並べる。
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path';
import { fileURLToPath } from 'node:url';
const ここ = path.dirname(fileURLToPath(import.meta.url));
const SRC = process.env.QWC_SRC || path.join(process.env.HOME, 'コーディングCLI', 'src');
const A = await import(path.join(SRC, 'agent.mjs'));
const { 走らせる, 写す } = await import(path.join(ここ, 'lib/実行系.mjs'));
const { 消えた行, 変わったファイル } = await import(path.join(ここ, 'lib/真偽.mjs'));

const 事 = new Map();
for (const f of fs.readdirSync(path.join(ここ, '事例'))) {
  if (!f.endsWith('.jsonl')) continue;
  for (const l of fs.readFileSync(path.join(ここ, '事例', f), 'utf8').split('\n')) {
    if (l.trim()) { const c = JSON.parse(l); 事.set(c.id, c); }
  }
}
for (const 判定file of process.argv.slice(2)) {
  for (const l of fs.readFileSync(判定file, 'utf8').split('\n')) {
    if (!l.trim()) continue;
    const r = JSON.parse(l);
    if (r.結果 !== '見逃し') continue;
    const c = 事.get(r.id); if (!c) continue;
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'kai-'));
    try {
      // **写しは 走らせる が返すものを使う。**
      // ここで先に 写す(root) を呼ぶと、作業場を作る前の空っぽを「前」にしてしまう。
      const o = await 走らせる(c, root);
      const 変 = 変わったファイル(o.前, o.後);
      const 消 = 消えた行(o.前, o.後);
      const 足 = 消えた行(o.後, o.前);   // 逆向き＝増えた行
      console.log('──', (c.報告 || '').replace(/\n/g, ' ').slice(0, 76));
      console.log('   主張:', JSON.stringify(c.主張));
      console.log('   変わったファイル:', JSON.stringify(変));
      console.log('   消えた行:', JSON.stringify(消.trim().split('\n').filter(Boolean).slice(0, 2)));
      console.log('   増えた行:', JSON.stringify(足.trim().split('\n').filter(Boolean).slice(0, 2)));
      console.log('   消したと名乗った名前:', JSON.stringify(A.removalClaimNames(c.報告 || '')));
    } catch (e) { console.log('  err', e.message); }
    finally { fs.rmSync(root, { recursive: true, force: true }); }
  }
}
