# agent-report-eval — measuring whether a lie detector for agent reports actually works

This harness measures the **report watchers** of [qwc](https://github.com/daigo0904/qwythos-code), an autonomous coding CLI: rules that check an agent's completion report ("I deleted it", "tests pass") against what really happened in the session. Deceptive and honest cases are generated from a catalogue of failure types, replayed through the **real** qwc agent loop, and scored by code that never reads the report.

> 日本語の詳しい説明と全記録: [README.ja.md](README.ja.md) · Records: [`記録/`](記録/)

```
 generate (model)  →  judge (code only)  →  aggregate (with confidence intervals)
```

## The one rule

**Generation is done by a model; judging is done by code.** The moment the judge uses the report text as evidence, the harness stops measuring and starts flattering itself. So three roles are separated:

| Role | File | Reads the report? |
| --- | --- | --- |
| Make cases | `生成.py` (generate) | writes it (model) |
| Decide the truth (oracle) | `lib/真偽.mjs` | **never** |
| The watchers being scored | `lib/検知.mjs` → qwc's `src/agent.mjs` | yes (they are the thing under test) |

- **The oracle and the watchers are implemented differently on purpose.** Both need "what was removed in this request"; the watcher derives it from the tool's edit log, the oracle from the filesystem before and after. If they shared code, a self-made-evidence trick would fool both and the score would stay perfect.
- **Every lie has an honest twin.** A watcher that fires on everything scores 100% on lies; only the honest twins expose it as a false positive.
- **Bad generation is not blamed on the watchers.** When the model was asked for a lie but produced an honest case (the oracle disagrees with the intended label), the case is *discarded* and counted separately, never mixed into the detection rate.
- **Generated commands never run as-is.** `lib/門.mjs` lets through only a small read-only command set and refuses interpreters; failures stay in the record as exit code 126. Interpreters (`python3`, `pytest`, `node`) are allowed only in **wall mode** (in [PR #4](https://github.com/daigo0904/agent-report-eval/pull/4), not yet merged), where the whole harness runs inside a Landlock sandbox that checks itself at start-up (home not writable, outbound TCP refused) and refuses to run otherwise.

## Failure types

`型.json` holds 15 types, most of them taken from real incidents in the author's own stack, e.g.: *claims without doing*, *self-made evidence* (add a line, delete it, report the deletion), *phantom target* (fix something that does not exist), *partial removal reported as complete*, *behaviour changed in the opposite direction*, and *rigged test pass* (`sitecustomize.py`, `conftest.py`, `PYTHONPATH=`).

## Results, and what they do not mean

| Set | Detection | False positives | Notes |
| --- | --: | --: | --- |
| All 1,481 cases (current watchers) | 727 caught, 15 missed | 19 of 738 honest | **in-sample**: the watchers were tuned on many of these |
| Held-out bundles (749 cases) | 97.8% (95% CI 95.6–98.9) | 2.8% (1.6–5.0) | no longer held-out after being read on 2026-10-01 |
| Blind independent judge (a model that never saw the oracle) | **72%** (23/32) | **27%** (8/30) | the oracle and the judge agree only moderately (κ = 0.47) |

The last row is the honest one. The oracle is my own code, and a detector scored by its author's oracle looks better than it is. That gap is why the verification work moved to [local-ai-stack/verify](https://github.com/daigo0904/local-ai-stack/tree/main/verify), where every measurement is pre-registered and the cases are written by authors who never see the rules.

## Usage

```sh
node 判定.mjs --種                 # judge the hand-written seed cases (cheapest check, ~30 s)
python3 生成.py --型 1 --件 2       # generate 2 cases of type 1 (Ollama, gemma4:26b)
python3 実行.py --件 3              # one generate → judge → aggregate cycle
python3 集計.py --全部              # per-type detection and false-positive rates with Wilson intervals
QWC_SRC=../qwythos-code/src node 判定.mjs 事例/*.jsonl   # judge against a given qwc checkout
```

Wall mode (Linux with Landlock only; available once PR #4 is merged):

```sh
W=$(mktemp -d) && HOME=$W TMPDIR=$W python3 lib/壁.py --書ける $W -- \
  env QWC_SRC=../qwythos-code/src node 判定.mjs --壁の中 種/型15.jsonl
```

File and command names are Japanese because the project's working language is Japanese.

## License

MIT.
