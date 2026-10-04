# LangGraph vs a plain state machine

Same agent, two engines. Both share tools, policy, and the audit store. A differential test (tests/test_graph.py) checks that scripted runs produce identical status, steps, tokens, and audit logs.

## Measured
- Lines of code: plain loop 106 lines, graph module 116 lines (plus a 39-line shared helper used by the graph engine). The framework did not reduce code at this size.
- LangGraph version tested: 1.2.12.
- qwen3-8b-8k, 3 runs per engine, one scenario: all 6 runs finished `done` with 0 failed actions in 3 steps. Graph runs were identical (4 executed, 1 queued, 6623 tokens). Two of three plain runs matched them. The first plain run differed (5 executed, 6547 tokens), the same as the first run in Phase 3. The cause is not established.
- llama3.1, 3 runs per engine: all 6 runs ended `ungrounded` in 2 steps and 2720 tokens. The grounding guard caught every one, under both engines.
- Evidence: docs/runs/qwen3-8b-8k-*-demo*.txt and docs/runs/llama3.1-*-demo*.txt.

## What the framework gave
- Checkpoints per step, keyed by thread, with no extra code in the nodes.
- A natural place to add human-in-the-loop interrupts and replay.
- An explicit graph shape that is easy to draw and review.

## What it cost
- State must be serializable, so the DB handle, model, and callbacks live in closures instead of state.
- Termination logic spreads across node return values and routing functions.
- One more dependency with fast-moving APIs. The prebuilt agent helper was deprecated in the v1 line in favor of a LangChain function.
- Stack traces pass through framework code.

## When I would use which
- Plain loop: one agent, one loop, bespoke policy, strict control of every step, a small team, and code you can read in one sitting.
- Graph framework: several agents or branches, long-running work that must pause and resume, human approval mid-run, or a team that already knows it.
- Decision rule: start plain. Move to a graph when you need pause/resume or branching and have a failing case that proves it.

## Not tested here
- Parallel branches, sub-graphs, persistent (SQLite or Postgres) checkpointers, streaming, and anything beyond a single scenario.
- The model mattered more than the engine in every run.
