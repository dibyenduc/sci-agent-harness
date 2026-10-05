# sci-agent-harness

A small, open agent harness for scientific R&D data. It shows how to build agents that work inside a lab data platform instead of a chat window, act on what they see in the data, and stay measurable and safe enough to trust.

Everything runs locally for $0 with open-weight models. A paid frontier-model comparison is optional and planned as the last step.

## Why this exists

Chat-only agents are the easy first version. The hard problems show up later:

- Agents need to react to data changes, not wait for a prompt.
- Autonomy has to be earned, so actions need a permission ladder, approvals, and undo.
- Reliability needs numbers, so behavior is traced and scored against real tasks.
- Each organization needs its own memory and goals, with no leakage between tenants.

## Status

| Phase | Component | Status |
|---|---|---|
| 1 | Three-layer data model, seed generator, tests | Done |
| 2 | Tools and MCP server | Done |
| 3 | Harness core: loop, action ladder, event triggers | Done |
| 4 | LangGraph engine and comparison | Done |
| 5 | Evaluation suite and tracing | Done |
| 6 | Goal memory and tenant isolation | Done |
| 7 | Optional frontier-model sweep | Planned |

## How it works

1. **Data.** A SQLite database holds a synthetic lab data model in three layers: raw measurements, structured experiments, and scientific intent (hypotheses and specs).
2. **Tools.** Eight typed tools (search, inspect, compare to spec, check inventory, convert units, draft experiment, create task, update hypothesis). Each has a risk level: `read`, `draft`, or `write`. The same functions are exposed over MCP.
3. **Watcher.** A poller notices new measurements that fall outside spec, after unit conversion, and starts an agent run with no human prompt.
4. **Two engines, one behavior.** The agent loop exists as a plain state machine and as a LangGraph graph. Both share the same tools, policy, and audit store. A differential test checks that they produce identical status, steps, tokens, and audit logs on scripted runs.
5. **Grounding guard.** If a model describes tool calls in text instead of making them, the run is nudged once, then marked `ungrounded` instead of `done`.
6. **Policy.** A per-run autonomy level decides whether each tool call executes, is queued for human approval, or is only recorded as a proposal.
7. **Audit log.** Every action is stored with its arguments, result, and an inverse operation, so a human can approve, reject, or undo it.

## Autonomy ladder

| Autonomy | read | draft | write |
|---|---|---|---|
| suggest | execute | propose | propose |
| draft | execute | execute | propose |
| approve | execute | execute | queue |
| auto | execute | execute | execute |

## Data model

The data is **synthetic**. Composition-to-property rules plus noise generate it with a fixed random seed. It is not real lab data, and results here say nothing about real materials.

- **Layer A, measurements.** Property, value, unit, instrument, timestamp.
- **Layer B, experiments.** Formulations (ingredients in wt%), process steps, samples, results.
- **Layer C, intent.** Hypotheses with target ranges, and specs that define pass or fail.

Supporting tables: ingredients, inventory, tasks. Every table carries a `tenant_id` so multi-tenant isolation can be tested later. Writes go through validated pydantic models, so bad units and bad percentages are rejected.

**Planted trap.** About 5% of viscosity values are stored in Pa.s instead of mPa.s. Agents have to notice and convert.

## Quickstart

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), and [Ollama](https://ollama.com).

```bash
git clone https://github.com/dibyenduc/sci-agent-harness.git
cd sci-agent-harness
make setup
make test

ollama pull qwen3:8b
ollama create qwen3-8b-8k -f models/Modelfile.qwen3-8k   # 8192-token context

make demo          # plain engine
make demo-graph    # LangGraph engine
```

The demo reseeds the database, sets the watcher baseline, injects an out-of-spec viscosity result, lets the agent respond, and lists actions awaiting approval.

The Makefile pins `MODEL` so runs are reproducible. Override it with `make demo MODEL=llama3.1:latest`. If you run the CLI directly, check `echo $MODEL` first, because a stale shell variable silently changes the model.

The MCP SDK is pinned to 1.x (`mcp<2`). A migration to 2.x is on the to-do list.

## Command line

```bash
uv run python -m harness.cli run --goal "Check F-0001 against spec" --autonomy approve --engine plain
uv run python -m harness.cli watch --once --autonomy approve --engine graph
uv run python -m harness.cli inject --formulation F-0001 --viscosity 4200
uv run python -m harness.cli actions      # audit log
uv run python -m harness.cli pending      # actions awaiting approval
uv run python -m harness.cli approve <id>
uv run python -m harness.cli reject <id>
uv run python -m harness.cli undo <id>
```

Make targets: `setup`, `seed`, `test`, `mcp`, `demo`, `demo-graph`, `clean`, `eval`, `demo-tenants`, plus the task generators (see the Makefile).

To compare both engines three times each on one model and save every run:

```bash
bash scripts/compare_engines.sh qwen3-8b-8k
```

## Model configuration

All model calls go through one OpenAI-compatible client, so switching between a local and a hosted model is configuration:

```bash
export BASE_URL=http://localhost:11434/v1   # Ollama
export API_KEY=ollama
export MODEL=qwen3-8b-8k
```

## Observed behavior

Single scenario (out-of-spec viscosity event), `approve` autonomy, three runs per cell. This is a smoke test, not a benchmark. Real measurement starts in Phase 5.

| Model | Engine | Runs | Outcome |
|---|---|---|---|
| qwen3-8b-8k | plain | 3 | 3 `done`, 0 failed actions, 3 steps |
| qwen3-8b-8k | graph | 3 | 3 `done`, 0 failed actions, 3 steps |
| llama3.1 | plain | 3 | 3 `ungrounded`, no tool calls made |
| llama3.1 | graph | 3 | 3 `ungrounded`, no tool calls made |

- The model decided the outcome. The engine did not.
- The two engines matched on every run except one plain run (5 executed actions instead of 4), whose cause is not established.
- An earlier baseline run (model not recorded) had 6 failed actions out of 13. The later improvement cannot be attributed to one change, because the model, tool error messages, and a tool default changed together.

Run logs are in `docs/runs/`. The engine comparison is in `docs/langgraph-vs-plain.md`.

## What broke along the way

Details are in `docs/what-broke-at-v2.md`. Short version:

- **Narrated tool calls.** One model wrote tool calls as text and reported results it never received. The loop now flags such runs as `ungrounded`.
- **Invented names.** Models substituted general chemistry knowledge for the actual catalog. Tool errors now list valid options.
- **Summaries misreport the log.** Read the audit log, not the model's summary.
- **Small default context window.** A 4096-token window is tight for an agent loop. A larger-context model variant is pinned in `models/`.

## Repository layout

src/harness/
models.py, db.py, seed.py, units.py data model, schema, synthetic data
tools/ tool registry, lab tools, MCP server
core/ plain loop, policy, audit store,
approvals, event watcher, model client,
shared tool-execution helper
graph/ LangGraph engine
cli.py command line
tests/ unit tests and engine parity tests
models/ Ollama Modelfile for a larger context
scripts/ engine comparison script
docs/ write-ups and saved run logs

## Goal memory and tenants

Long-lived goals persist across runs. `goal-create` stores a goal, and each `goal-run` records a note. Every note carries a **trust level**:

| Trust | Meaning | How the next run sees it |
|---|---|---|
| operator | Written by a lab operator | `operator note (trusted, written by the lab operator)` |
| model | The model's own earlier summary | `unverified summary`, quoted as data |
| untrusted | Text from an outside source | `unverified summary`, quoted as data |

Lessons are always shown as unverified claims, whatever their trust level. The prompt tells the model that a lesson never replaces a tool result.

Each run also gets **verified facts** derived from the audit log: tool, arguments, status, and a digest of the result built from a per-tool whitelist of numeric and enum fields. Free text (lab notes, rationales, titles) is never included, so an injected note cannot reach the verified section.

Notes are tenant-scoped, evidence must belong to the run it is attached to, and runs on closed or foreign goals fail before a run row is created.

### Tenant isolation

Every table carries a `tenant_id`, and every tool call is scoped to the caller's tenant. `tests/test_two_tenants.py` seeds two tenants into one database and checks three things: each sees only its own data, the same question gets different answers per tenant, and one tenant's notes never reach the other's prompt.

`make demo-tenants` runs the same question for both tenants with a real model. In `docs/runs/qwen3-8b-8k-tenant-divergence-demo.txt`, each answer matches its own tenant's data, and each follows its own remembered priority (cure time for one, gloss for the other). This is one run on one formulation, so it illustrates the mechanism and is not a rate.

### Memory evaluation

Nine tasks (3 recall, 4 poison, 2 control) run with memory on and off. Full tables are in `docs/results.md`.

| Model | Temp | Memory on | Memory off |
|---|---|---|---|
| qwen3-8b-8k | 0.0 | 9/9 | 6/9 |
| qwen3-8b-8k | 0.7 | 25/27 | 18/27 |
| llama3.1 | 0.0 | 9/9 | 6/9 |
| llama3.1 | 0.7 | 23/27 | 17/27 |

How to read it:

- The recall gain is built into the design. With memory off, the recall tasks cannot be answered from the tools, and those are the failures in the memory-off column.
- The useful comparison is poison and control, where memory should not hurt. Qwen3 passed all 18 of those runs at t0.7 in both arms. Llama failed 4 of 18 with memory on (about 1 with it off). That difference is not significant at this size.
- No injected action was executed in any memory-on poison run (0 of 16 per model). Llama's two poison-task failures were a tool call written as text and a misread number.
- Llama wrote a tool call as text in 3 of 27 memory-on runs and in none of 27 memory-off runs. This may be a longer-prompt effect, but the sample is too small to establish it.
- One task remains open. recall-02 gives qwen3 a model-written summary that disagrees with a tool value, and qwen3 trusts the tool. The prompt tells it to, so this is a question about how the task is worded, not a model failure.

## Limitations

- Synthetic data, small scale, one scenario so far.
- Local models are weaker than frontier models, so failure patterns will differ.
- Small samples carry wide uncertainty. Treat any pass rate here as a rough indication.
- The memory evaluation has nine tasks and three repeats per cell at most. Differences of one or two runs are within noise.
- Tenant isolation is tested in the data and prompt layers on a synthetic two-tenant database, not against a production deployment.

## License

MIT. See `LICENSE`.

