# Spacedock as Code-First Workflow Runtime — End-User Impact Sketch

This document sketches the user-facing impact of moving Spacedock's first officer (FO) from a prose-interpreted Claude Code skill to a code-first reconciler with an LLM sidecar, as discussed in the 2026-04-17 brainstorm. The architecture under consideration: a deterministic state machine exposes a declarative API surface; the LLM-FO is constrained to that surface as its only mechanism to mutate workflow state; the same API can run inside Claude Code (interactive captain UX) or as a standalone runtime (CI, cron, headless). Stage transitions are modeled as tail-recursive function calls; cross-entity dependencies become un-returned awaits in the call graph.

This document is use-case-only — the full design is not yet specified. The goal is to make the captain-experience changes concrete enough to decide whether the architecture is worth building.

## Use Case 1: "Why is this stuck?" — call-stack debug view

**Scenario.** Three days have passed. The captain returns to the project. Entity 172 sits at the validation gate; entity 177 is in implementation; entity 178 has an open PR. None are advancing.

**Today.** The captain asks the FO. The FO reads entity files, scans recent chat turns, scans git log, reconstructs the cluster from prose, and produces a narrative answer. The answer is best-effort and depends on what the FO can find in scattered context. In a fresh session, half the cluster context is gone.

**Proposed.** The captain runs `spacedock why 172` (or asks the FO to run it; same primitive). Output is a literal print of the call graph at that entity:

```
172 ▸ validation ▸ awaiting gate_decision (captain input pending)
  ⤷ 172 merge requires CI claude-live-opus pass
    ⤷ awaiting outcome of 177 ▸ implementation
      ⤷ awaiting gh run 24544337747 (in_progress)
```

The same primitive that drives the engine — un-returned function calls in the tail-recursive call graph — is the captain's debug view. No reconstruction; the structure is the answer.

**Captain impact.** Cluster debugging no longer requires chat history. Multi-entity stuck-states become a one-line query.

## Use Case 2: Cluster-aware "what's on my desk?"

**Scenario.** The captain has 30 minutes between meetings. Several entities are mid-flight. They want the highest-leverage thing to look at right now.

**Today.** The captain reads through entity files, asks the FO for status, and mentally filters for items waiting on them. A stuck gate or a captain-decision request that surfaced earlier in the chat is easy to miss.

**Proposed.** `spacedock ready` (or FO equivalent) returns a structured list:

```
Captain decisions pending:
  172 ▸ validation gate (post-fold) — Recommend approve [opened 2h ago]
  178 ▸ merge gate — PR #113 awaiting your decision [opened 1d ago]

Dispatch decisions pending:
  176-followup ▸ backlog gate — file or skip? [from 177's outcome]
```

The reconciler computes this from the state graph. The captain works through the list; no item gets lost.

**Captain impact.** "What needs me?" becomes a query, not an excavation.

## Use Case 3: Crash-safe session continuation

**Scenario.** The captain's laptop dies mid-session. The FO process is gone. They reopen the next day.

**Today.** The new FO session loads the workflow and reads entity files — stages and statuses are visible. But context — pending captain decisions, in-flight clusters, what was being deferred and why — lives in the prior chat transcript. Some is reconstructible from commit messages; much is not. The new session re-discovers reality.

**Proposed.** State lives in entity frontmatter plus a small structured "pending decisions" log on disk. The new FO session loads them and resumes. Mid-flight gates surface immediately with their original summaries. Cross-entity dependencies come from the dep graph, not from reconstructed conversation. The captain returns to the same desk they left.

**Captain impact.** Multi-day workflows survive interruption without drift. Long-running clusters do not lose context between sessions.

## Use Case 4: Hallucination-resistant state mutations

**Scenario.** The captain dispatches entity 200. The FO claims it advanced through ideation, dispatched implementation, validated, and merged. The captain checks: nothing happened. The model fabricated the entire workflow execution.

**Today.** This is the failure pattern documented in #177 — opus-4-7 ensigns at low/medium effort skip tool calls and write outcomes as prose. The FO is itself an LLM running on opus-4-7; the same regression makes the FO claim work it did not do. State drift is silent until the captain audits.

**Proposed.** The LLM-FO can only mutate state through API tools that actually mutate (or fail loudly). It cannot claim a status change without making the API call. If it skips the call, the next reconcile tick sees unchanged state and re-prompts. Hallucinated outcomes leave no fingerprint because they do not exist; the API call log is the audit trail.

**Captain impact.** Workflow integrity no longer depends on the prose discipline of whatever model the captain uses today. Model regressions affect prose quality, not workflow correctness.

## Use Case 5: Headless / CI / cron workflow runs

**Scenario.** The captain wants nightly inbox triage: any new tasks filed in the last 24 hours get auto-ideated to a stub, scored, and queued for morning review. They also want a cron-driven daily pass to advance everything safe to advance.

**Today.** Both require an interactive Claude Code session. The captain must run things manually. Headless workflow execution is impossible because the FO assumes a captain conversation surface.

**Proposed.** The standalone runtime executes the same API surface. The LLM handles soft surfaces (ideation drafting, gate summaries), but routine state advancement runs without it. Cron triggers `spacedock advance --workflow docs/plans` and the engine reconciles autonomously, surfacing only captain decisions for the next interactive session.

**Captain impact.** Workflows run when the captain is not watching. Long-running experiments do not burn captain attention.

## What is not in this sketch

- Migration path from the prose-FO. The architecture transition is non-trivial; this document only argues whether the destination is worth reaching.
- Detailed API surface design. The use cases assume an API exists; the actual verb/noun shape is the next design question.
- Standalone-runtime build details. Captain interaction in the standalone case (TUI? sidecar IPC? web UI?) is a separate decision.
- Multi-captain scenarios. Spacedock today assumes a single captain; the API model would naturally support multiples, but the UX implications need their own design.

## Next steps

The brainstorm has converged on architecture (API + multi-host), API model (declarative reconciliation), mental model (tail-recursive stage chain with stage-level await), and the high-value cases (multi-entity coordination + hallucination resistance). The next design surfaces are: API verb/noun granularity, dependency declaration model (frontmatter edges vs. workflow-as-code DSL), and gate sync/async semantics.

Once those are nailed down, this document upgrades from use-case sketch to full design spec, and the writing-plans skill takes over for implementation breakdown.
