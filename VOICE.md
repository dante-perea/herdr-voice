# Herdr Voice (Grok Think Fast 2.0)

This fork adds a launchable voice-control path under [`voice/`](./voice/).

## Quick start

1. Start herdr (a session server must be running).
2. Install Python deps and set your key:

```powershell
cd voice
python -m pip install -r requirements.txt
$env:XAI_API_KEY = "xai-..."
python -m herdr_voice
```

3. Press **``** (backtick twice) and speak a command.
4. Press **`** (backtick once) to end the turn.

Without `XAI_API_KEY`, the process exits with a clear message (fail-closed).

## Model

- **Default model id:** `grok-voice-think-fast-2.0`
- **Endpoint:** `wss://api.x.ai/v1/realtime?model=grok-voice-think-fast-2.0`
- **Auth env:** `XAI_API_KEY`
- Manual PTT (`turn_detection: null`) — not continuous server VAD alone.

## Control surface

Grok is given function tools that shell out to real `herdr` CLI commands:

`workspace *`, `tab *`, `pane *`, `agent *`, and a composite `session_snapshot`.

See [`voice/README.md`](./voice/README.md) for the full tool list and architecture.
