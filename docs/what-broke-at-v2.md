# What broke at v2

Failures found while building this harness, with the fix and the lesson for each. Run logs are in docs/runs/.

## 1. Narrated tool calls (hallucinated actions)
- **Symptom:** An event-triggered run ended with status "done" after one step. The final answer listed JSON "function calls" as text and claimed to have retrieved data and created a task. The audit log had zero actions.
- **Cause:** The model (llama3.1) did not use the structured tool-calling interface. It wrote calls as prose, then invented the results.
- **Fix:** Track whether any tool was actually invoked. If the model names tools in text without calling them, or an event-triggered run ends with no actions, nudge once, then mark the run "ungrounded" instead of "done".
- **Lesson:** Success status must come from the audit log, not from the model's own summary.
- **Evidence:** docs/runs/run-ungrounded-example.txt

## 2. Invented names, duplicate proposals, guessed IDs
- **Symptom:** 6 of 13 actions in one run failed on invented names: three spec names ("viscosity", "Viscosity", "Viscosity (mPa.s)") instead of the default coating_std, and two ingredients ("silicone oil", "polyester resin") that are not in the catalog. One queued write was duplicated, and the model guessed a hypothesis ID that did not exist. It also proposed refuting a hypothesis nobody asked about.
- **Cause:** The model substituted general domain knowledge for the tenant's actual catalog. Errors only said "not found," so it varied the guess instead of changing strategy.
- **Fix:** Errors now list valid options. The default spec is stated in the tool description. Identical pending writes collapse into one queue entry. The approval queue stopped the unrequested judgment call.
- **Lesson:** Error messages are part of the prompt. Autonomy limits matter most for actions the model chose on its own initiative.
- **Evidence:** docs/runs/run1-baseline.txt. After the fixes, with qwen3:8b, three runs had 0 failed actions (docs/runs/qwen3-8b-8k-demo1.txt to demo3.txt). The model also changed, so the improvement cannot be credited to the fixes alone.

## 3. Summaries misreport the audit log
- **Symptom:** In one run that ended "done," the summary said a draft experiment was pending approval and that a task had been created. In the audit log the draft was executed (drafts run at the approve level) and the task was only queued.
- **Cause:** The model describes what it intended, not what the policy layer decided, and it paraphrases tool statuses loosely.
- **Fix:** The CLI prints the audit log for every run next to the summary. Phase 5 evals will score claims in the final text against logged actions.
- **Lesson:** Humans and graders should read the log. The summary is a convenience, never evidence.

## 4. Small default context window
- **Symptom:** `ollama ps` showed a 4096-token context while a three-step run used about 6,500 tokens in total.
- **Cause:** The default window is small for an agent loop with tool schemas and a growing history. Overflow can silently drop the oldest content.
- **Fix:** A Modelfile variant with an 8192-token context (models/Modelfile.qwen3-8k), pinned in the Makefile.
- **Lesson:** Record the model name and context size with every run. Otherwise results are not comparable.
