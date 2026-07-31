"""Config / model pin tests for Grok Voice Think Fast 2.0."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herdr_voice.config import DEFAULT_MODEL_ID, XAI_REALTIME_URL, VoiceConfig
from herdr_voice.grok_client import GrokVoiceClient
from herdr_voice.herdr_control import HerdrController


def test_default_model_is_think_fast_2():
    assert DEFAULT_MODEL_ID == "grok-voice-think-fast-2.0"
    assert "grok-voice-think-fast-2.0" in XAI_REALTIME_URL
    assert XAI_REALTIME_URL.startswith("wss://api.x.ai/v1/realtime")


def test_voice_config_realtime_url_pins_model():
    cfg = VoiceConfig(model_id="grok-voice-think-fast-2.0")
    assert cfg.realtime_url() == (
        "wss://api.x.ai/v1/realtime?model=grok-voice-think-fast-2.0"
    )


def test_session_update_disables_server_vad_for_ptt():
    client = GrokVoiceClient(
        VoiceConfig(),
        api_key="test-key",
        controller=HerdrController(),
    )
    payload = client.session_update_payload()
    assert payload["type"] == "session.update"
    session = payload["session"]
    assert session["turn_detection"] is None
    assert any(t.get("name") == "workspace_create" for t in session["tools"])
    assert any(t.get("name") == "session_snapshot" for t in session["tools"])
