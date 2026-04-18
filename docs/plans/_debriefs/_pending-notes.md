# Pending debrief notes

Observations captured during sessions that the next debrief should consume. Clear this file after incorporating.

---

## 2026-04-18 — context-exhausted subagent resisted shutdown

**Observation:** #188 implementation ensign hit 101.8% of its 200k context limit (`reuse_ok: false` per `claude-team context-budget`). When FO sent `shutdown_request`, the ensign did not terminate promptly — it continued emitting idle notifications for ~30+ minutes after the first shutdown request. Only terminated cleanly after a second shutdown request sent alongside the fresh-dispatch of its replacement.

**Investigation needed — two distinct questions:**

1. **Is this a Claude Code behavior change?** In prior sessions across the fleet this session (earlier shutdowns of #183, #184, #185, #186 ensigns all terminated within seconds). Was opus-4-7 specifically different on shutdown response when context-full? Or did Claude Code's subagent lifecycle semantics change?

2. **Did the subagent actually launch `opus[1m]`?** The `context-budget` output showed:
   ```
   config_declared_model: "opus[1m]"
   config_drift_warning: "team config requested opus[1m] but runtime is claude-opus-4-7"
   ```
   Team config wanted the 1M-context variant (`opus[1m]`) but the runtime fell back to `claude-opus-4-7` (standard 200k context). If the fallback is silent, we never get the 1M budget the config requested — investigate why the fallback happens and whether `opus[1m]` is a real model identifier Claude Code recognizes at dispatch time.

**Reference session:** captain-session `spacedock-plans-20260417-2342-f26a6ff0`, ensign `spacedock-ensign-streaming-watcher-over-filesystem-polling-implementation`.

**Evidence locations:**
- `claude-team context-budget` output captured mid-session (contains the 101.8% reading)
- Session chat log covering `~06:09-06:43Z` shows the idle-notification spate during the resistance-to-shutdown period
- The `config_drift_warning` is emitted by the `claude-team` helper itself — source probably indicates what constitutes drift

**Action:** next debrief should either file a follow-up entity to investigate, or (if quick) resolve in the debrief's own investigation.
