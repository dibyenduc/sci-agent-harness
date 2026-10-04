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
| 4 | LangGraph variant and comparison | Planned |
| 5 | Evaluation suite and tracing | Planned |
| 6 | Goal memory and tenant isolation | Planned |
| 7 | Optional frontier-model sweep | Planned |

## How it works

1. **Data.** A SQLite database holds a synthetic lab data model in three layers: raw measurements, structured experiments, and scientific intent (hypotheses and specs).
2. **Tools.** Eight typed tools (search, inspect, compare to spec, check inventory, convert units, draft experiment, create task, update hypothesis). Each has a risk level: `read`, `draft`, or `write`. The same functions are exposed over MCP.
3. **Watcher.** A poller notices new measurements that fall outside spec, after unit conversion, and starts an agent run with no human prompt.
4. **Loop.** A bounded agent loop with a step cap, a token budget, a repeated-call detector, and a grounding guard that flags runs where the model describes tool calls in text instead of making them.
5. **Policy.** A per-run autonomy level decides whether each tool call executes, is queued for human approval, or is only recorded as a proposal.
6. **Audit log.** Every action is stored with its arguments, result, and an inverse operation, so a human can approve, reject, or undo it.

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
git clone [https://github.com/dibyenduc/sci-agent-harness.git](https://github.com/dibyenduc/sci-agent-harness.git)
cd sci-agent-harness
make setup
make test

ollama pull qwen3:8b
ollama create qwen3-8b-8k -f models/Modelfile.qwen3-8k   # 8192-token context

make demo
```

`make demo` reseeds the database, sets the watcher baseline, injects an out-of-spec viscosity result, lets the agent respond, and lists actions awaiting approval.

The Makefile pins `MODEL` so runs are reproducible. Override it with `make demo MODEL=llama3.1:latest`.

The MCP SDK is pinned to 1.x (`mcp<2`). A migration to 2.x is on the to-do list.

## Command line

```bash
uv run python -m harness.cli run --goal "Check F-0001 against spec" --autonomy approve
uv run python -m harness.cli watch --once --autonomy approve
uv run python -m harness.cli inject --formulation F-0001 --viscosity 4200
uv run python -m harness.cli actions      # audit log
uv run python -m harness.cli pending      # actions awaiting approval
uv run python -m harness.cli approve <id>
uv run python -m harness.cli reject <id>
uv run python -m harness.cli undo <id>
```

Make targets: `setup`, `seed`, `test`, `mcp`, `demo`, `clean`.

## Model configuration

All model calls go through one OpenAI-compatible client, so switching between a local and a hosted model is configuration:

```bash
export BASE_URL=http://localhost:11434/v1   # Ollama
export API_KEY=ollama
export MODEL=qwen3-8b-8k
```

## Observed behavior (Phase 3)

Single scenario (out-of-spec viscosity event), `approve` autonomy, local model `qwen3:8b` with an 8192-token context. Three runs: all finished `done` with 0 failed actions (4–5 executed, 1 queued for approval). An earlier baseline run (model not recorded) had 6 failed actions out of 13. The improvement cannot be attributed to one change, because the model, tool error messages, and a tool default changed together. Three runs of one scenario is a smoke test, not a benchmark. Real measurement starts in Phase 5.

Run logs are in `docs/runs/`.

## What broke along the way

Details are in `docs/what-broke-at-v2.md`. Short version:

- **Narrated tool calls.** One model wrote tool calls as text and reported results it never received. The loop now flags such runs as `ungrounded`.
- **Invented names.** Models substituted general chemistry knowledge for the actual catalog. Tool errors now list valid options.
- **Summaries misreport the log.** Read the audit log, not the model's summary.

## Repository layout

src/harness/
models.py, db.py, seed.py, units.py data model, schema, synthetic data
tools/ tool registry, lab tools, MCP server
core/ loop, policy, audit store, approvals,
event watcher, model client
cli.py command line
tests/ unit tests
models/ Ollama Modelfile for a larger context
docs/ write-ups and saved run logs


## Limitations

- Synthetic data, small scale, one scenario so far.
- Local models are weaker than frontier models, so failure patterns will differ.
- Small samples carry wide uncertainty. Treat any pass rate here as a rough indication.

## License

MIT. See `LICENSE`.

