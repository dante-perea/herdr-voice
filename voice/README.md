# herdr-voice

Hands-free control of [herdr](https://herdr.dev) using **Grok Voice Think Fast 2.0** (`grok-voice-think-fast-2.0`) via the xAI realtime Speech-to-Speech API.

This directory is part of the **herdr-voice** fork (`dante-perea/herdr-voice`).

## Push-to-talk contract

| Keys | Action |
|------|--------|
| <code>``</code> (two backticks) | Start listening / speak your command |
| <code>`</code> (one backtick) | End turn and submit to Grok |

Server-side VAD is **disabled**. Turn boundaries are fully controlled by these hotkeys so you can speak free-handed without the model cutting you off.

## Prerequisites

1. A running **herdr** session (this controller shells out to the `herdr` CLI / socket API).
2. An **xAI API key** with Voice access.
3. Python 3.10+.

```powershell
cd voice
python -m pip install -r requirements.txt
$env:XAI_API_KEY = "xai-..."   # https://console.x.ai/
```

Optional:

```powershell
$env:HERDR_BIN = "C:\Users\...\Herdr\bin\herdr.exe"
$env:HERDR_VOICE_MODEL = "grok-voice-think-fast-2.0"  # default
```

## Run

```powershell
cd voice
python -m herdr_voice
```

Dry-run (no key / no network):

```powershell
python -m herdr_voice --dry-run-config
```

## What Grok can control

Function tools map to real herdr CLI argv:

- **Workspaces / spaces** — list, create, focus, rename, close  
- **Tabs** — list, create, focus, rename, close  
- **Panes** — list, split, focus, close, read, send-text, run  
- **Agents** — list, start, prompt, focus, wait, attach, read  
- **Session snapshot** — status + sessions + workspaces + tabs + panes + agents  

Examples you can say after <code>``</code>:

- “Create a new space called demo”
- “Open a tab labeled tests”
- “Split the pane down”
- “Start a claude agent named coder on pane w1:t1:p2”
- “Snapshot the session”

Then press <code>`</code> once to submit.

## Tests

```powershell
cd voice
python -m pytest -q
```

## Architecture

| Module | Role |
|--------|------|
| `ptt.py` | `` / ` turn state machine |
| `hotkey.py` | Global backtick listener (pynput) |
| `herdr_control.py` | Argv builders + intent dispatch to `herdr` |
| `tools.py` | Grok function-tool schemas |
| `grok_client.py` | xAI `wss://api.x.ai/v1/realtime` client |
| `audio_io.py` | Mic capture / speaker playback |
| `main.py` | Entry point |

Default model id is pinned to **`grok-voice-think-fast-2.0`**. Pricing is usage-based on xAI ($0.08/min audio at launch of 2.0 — see [xAI pricing](https://docs.x.ai/developers/pricing)).
