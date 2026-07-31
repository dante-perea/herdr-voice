"""Runtime configuration for herdr-voice (Grok Voice Think Fast 2.0)."""

from __future__ import annotations

import os
from dataclasses import dataclass

# Pinned default — do not silently swap to another provider.
DEFAULT_MODEL_ID = "grok-voice-think-fast-2.0"
XAI_REALTIME_BASE = "wss://api.x.ai/v1/realtime"
XAI_REALTIME_URL = f"{XAI_REALTIME_BASE}?model={DEFAULT_MODEL_ID}"

DEFAULT_VOICE = "eve"
DEFAULT_SAMPLE_RATE = 24000
API_KEY_ENV = "XAI_API_KEY"
HERDR_BIN_ENV = "HERDR_BIN"
DEFAULT_HERDR_BIN = "herdr"

# Double-backtick window for start-of-turn (ms).
DOUBLE_BACKTICK_MS = 450


@dataclass(frozen=True)
class VoiceConfig:
    model_id: str = DEFAULT_MODEL_ID
    api_key_env: str = API_KEY_ENV
    voice: str = DEFAULT_VOICE
    sample_rate: int = DEFAULT_SAMPLE_RATE
    herdr_bin: str = DEFAULT_HERDR_BIN
    double_backtick_ms: int = DOUBLE_BACKTICK_MS

    @classmethod
    def from_env(cls) -> "VoiceConfig":
        return cls(
            model_id=os.environ.get("HERDR_VOICE_MODEL", DEFAULT_MODEL_ID),
            voice=os.environ.get("HERDR_VOICE_NAME", DEFAULT_VOICE),
            sample_rate=int(os.environ.get("HERDR_VOICE_SAMPLE_RATE", str(DEFAULT_SAMPLE_RATE))),
            herdr_bin=os.environ.get(HERDR_BIN_ENV, DEFAULT_HERDR_BIN),
            double_backtick_ms=int(
                os.environ.get("HERDR_VOICE_DOUBLE_BACKTICK_MS", str(DOUBLE_BACKTICK_MS))
            ),
        )

    def require_api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "").strip()
        if not key:
            raise SystemExit(
                f"Missing {self.api_key_env}. Set it to your xAI API key before starting "
                f"herdr-voice (model={self.model_id}).\n"
                f"  Windows PowerShell:  $env:{self.api_key_env} = 'xai-...'\n"
                f"  Get a key: https://console.x.ai/"
            )
        return key

    def realtime_url(self) -> str:
        return f"{XAI_REALTIME_BASE}?model={self.model_id}"


SYSTEM_INSTRUCTIONS = """You are Herdr Voice, a hands-free controller for the herdr terminal agent multiplexer.

You control herdr entirely through the provided tools (CLI surface). Prefer tools over guessing state.
Always call session_snapshot or list tools when you need current IDs before create/focus/close.

Capabilities:
- Workspaces (spaces): create, list, focus, rename, close
- Tabs: create, list, focus, rename, close
- Panes: list, focus, split, close, read, send text/keys, run commands
- Agents: list, start, prompt, focus, wait, attach, read
- Session: snapshot for full situational awareness

When the user speaks a command, execute it with tools immediately. Confirm briefly after success.
If a command needs an ID, resolve it from a fresh snapshot/list first.
Speak concisely. One short confirmation sentence after actions.
"""
