# herdr-voice stability defaults (frozen)

Source of truth for the stability implementation map. Change deliberately.

## CLI timeouts

| Case | Timeout | Behavior |
|------|---------|----------|
| Ordinary herdr tools (`list`, `focus`, `create`, …) | **30s** | `subprocess.run(timeout=…)` |
| Long tools (`agent_wait`, `pane_run`, agent start with `timeout_ms`) | Honor tool `timeout_ms` if set, else **120s** | Same |
| On timeout | Kill child; return `returncode=-1`, `stderr` with `error=timeout`, `error` field for Grok | Never hang unbounded |

Env overrides:

- `HERDR_VOICE_CLI_TIMEOUT_S` (default 30)
- `HERDR_VOICE_CLI_LONG_TIMEOUT_S` (default 120)

## WebSocket reconnect

- Enable **session resumption** on every connect (`session.resumption.enabled: true` in `session.update`).
- Persist `conversation.id` from `conversation.created`.
- Reconnect URL: `wss://api.x.ai/v1/realtime?model=<model>&conversation_id=<id>` when id known.
- Backoff: exponential **1s, 2s, 4s, … cap 30s**, infinite while process up (except fatal auth / missing key).
- After open: full `session.update` (voice, instructions, tools, `turn_detection: null`, audio, resumption).
- Operator signal: log + stdout line `herdr-voice: reconnecting…` / `herdr-voice: reconnected`.
- Mid-tool on dead socket: structured error to model when restored; do not block forever.

Env:

- `HERDR_VOICE_RECONNECT` = `1` (default on) / `0` to disable auto-reconnect
- `HERDR_VOICE_RECONNECT_CAP_S` (default 30)

## Fail-loud

| Failure | Behavior |
|---------|----------|
| Missing API key / websockets / pynput | Exit non-zero (fail closed) |
| Mic import or stream death | Set health flag; log ERROR; stderr banner; first listen reports failure |
| Speaker death | Health flag + ERROR; one automatic thread restart attempt |
| Hotkey listener dies | Log ERROR + **exit process** (operator restarts) |

Ready banner only prints when hotkeys started and WS connect succeeded.

## Tests / smoke

- Unit tests for timeout + reconnect policy + health flags under `voice/tests/`.
- Manual checklist: `voice/SMOKE.md`.
