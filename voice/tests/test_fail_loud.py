"""Fail-loud health flags (stability pillar 3)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herdr_voice.audio_io import MicCapture, SpeakerPlayback
from herdr_voice.hotkey import BacktickHotkeyListener
from herdr_voice.ptt import PttTurnMachine


def test_mic_starts_unhealthy_until_stream():
    mic = MicCapture(sample_rate=24000)
    assert mic.healthy is False
    assert mic.last_error is None


def test_speaker_starts_unhealthy_until_stream():
    spk = SpeakerPlayback(sample_rate=24000)
    assert spk.healthy is False


def test_hotkey_fatal_sets_unhealthy_and_calls_callback():
    machine = PttTurnMachine()
    seen: list[str] = []

    def on_event(_e):  # noqa: ANN001
        return None

    listener = BacktickHotkeyListener(
        machine, on_event, on_fatal=lambda r: seen.append(r)
    )
    listener.healthy = True
    listener._fatal("unit-test")
    assert listener.healthy is False
    assert seen == ["unit-test"]
