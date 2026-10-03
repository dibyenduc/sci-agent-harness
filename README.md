# sci-agent-harness

A small, open agent harness for scientific R&D data. It shows how to build agents that work inside a lab data platform instead of a chat window, act on what they see, and stay measurable and safe enough to trust.

Everything here runs locally for $0 using open-weight models. A paid frontier-model sweep is optional and planned as a final step.

## Why this exists

Chat-only agents are the easy first version. The hard problems show up later:

- Agents need to react to data changes, not wait for a prompt.
- Autonomy has to be earned, so actions need a permission ladder, approvals, and rollback.
- Reliability needs numbers, so every behavior is traced and scored against real tasks.
- Each organization needs its own memory and goals, with no leakage between tenants.

## Status

| Phase | Component | Status |
|---|---|---|
| 1 | Three-layer data model, seed generator, tests | Done |
| 2 | Tools and MCP server | Planned |
| 3 | Harness core: loop, action ladder, event triggers | Planned |
| 4 | LangGraph variant and comparison | Planned |
| 5 | Evaluation suite and tracing | Planned |
| 6 | Goal memory and tenant isolation | Planned |
| 7 | Optional frontier-model sweep | Planned |

## Data model

The data is **synthetic**. Composition-to-property rules plus noise generate it with a fixed random seed. It is not real lab data, and results here say nothing about real materials.

Three layers:

- **Layer A, measurements.** Raw instrument readings: property, value, unit, instrument, timestamp.
- **Layer B, experiments.** Formulations (ingredients in wt%), process steps, samples, and results.
- **Layer C, intent.** Hypotheses with target ranges, plus specs that define pass or fail.

Supporting tables: ingredients, inventory, tasks. Every table carries a `tenant_id` so multi-tenant isolation can be tested later.

Writes go through validated pydantic models. Units are checked per property, and formulation percentages must sum to 100.

**Planted traps.** About 5% of viscosity values are stored in Pa.s instead of mPa.s. This is deliberate. Later evals test whether agents notice and convert.

## Quickstart

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), and [Ollama](https://ollama.com) for local models (needed from Phase 2 on).

```bash
git clone https://github.com/dibyenduc/sci-agent-harness.git
cd sci-agent-harness
make setup
make seed     # builds lab.db: 9 ingredients, 200 formulations, 800 measurements
make test
```

Quick look at the data:

```bash
sqlite3 lab.db "select property, round(avg(value),1) from measurement group by property;"
```

## Model configuration

All model calls go through one OpenAI-compatible client. Switching between a local model and a hosted one is a config change:

```bash
export BASE_URL=http://localhost:11434/v1   # Ollama
export API_KEY=ollama
export MODEL=qwen3:8b
```

## Repository layout
src/harness/ models, database, seed generator (tools, core, memory to come)
tests/ unit tests
evals/ task sets, scorers, results (Phase 5)
docs/ architecture notes and design write-ups


## Design notes (planned write-ups)

- `docs/architecture.md`: components and data flow.
- `docs/langgraph-vs-plain.md`: when a framework helps and when a plain state machine wins.
- `docs/what-broke-at-v2.md`: real failures found while building, with fixes.

## Limitations

- Synthetic data, small scale.
- Local models are weaker than frontier models, so failure patterns will differ.
- Eval results from small task sets carry wide uncertainty. Reported variance matters more than any single pass rate.

## License

MIT. Add a `LICENSE` file before publishing.

