# herdr-voice smoke

## Automated (agent / CI)

```powershell
cd voice
# XAI_API_KEY from env or Infisical; herdr server running
python scripts/smoke_stability.py
```

Covers: pytest, CLI timeout kill path, reconnect backoff math, live xAI WS connect + resumption flag + `workspace_list` against real herdr.

## Live PTT (needs mic + human speech)

Only the double-backtick → speak → single-backtick path still needs a human mouth. Everything else is automated above.
