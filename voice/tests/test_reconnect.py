"""WebSocket reconnect / resumption policy (stability pillar 2)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herdr_voice.config import VoiceConfig
from herdr_voice.grok_client import GrokVoiceClient, reconnect_backoff_s
from herdr_voice.herdr_control import HerdrController


def test_backoff_exponential_capped():
    assert reconnect_backoff_s(0, cap_s=30) == 1
    assert reconnect_backoff_s(1, cap_s=30) == 2
    assert reconnect_backoff_s(2, cap_s=30) == 4
    assert reconnect_backoff_s(10, cap_s=30) == 30
    assert reconnect_backoff_s(3, cap_s=5) == 5


def test_session_update_enables_resumption():
    client = GrokVoiceClient(
        VoiceConfig(),
        api_key="test-key",
        controller=HerdrController(),
    )
    session = client.session_update_payload()["session"]
    assert session["turn_detection"] is None
    assert session["resumption"]["enabled"] is True


def test_realtime_url_includes_conversation_id_when_set():
    cfg = VoiceConfig(model_id="grok-voice-think-fast-2.0")
    assert cfg.realtime_url() == (
        "wss://api.x.ai/v1/realtime?model=grok-voice-think-fast-2.0"
    )
    assert cfg.realtime_url("conv-abc") == (
        "wss://api.x.ai/v1/realtime?model=grok-voice-think-fast-2.0&conversation_id=conv-abc"
    )


def test_client_url_uses_conversation_id():
    client = GrokVoiceClient(
        VoiceConfig(model_id="grok-voice-think-fast-2.0"),
        api_key="k",
        controller=HerdrController(),
    )
    client.conversation_id = "cid-1"
    assert "conversation_id=cid-1" in client.url


def test_conversation_created_stores_id():
    import asyncio

    client = GrokVoiceClient(
        VoiceConfig(),
        api_key="k",
        controller=HerdrController(),
    )

    async def run() -> None:
        await client._handle_event(
            {"type": "conversation.created", "conversation": {"id": "c-99"}}
        )

    asyncio.run(run())
    assert client.conversation_id == "c-99"
