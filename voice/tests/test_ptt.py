"""Unit tests for the real shipped PTT turn state machine."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `pytest` from voice/ without install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herdr_voice.ptt import PttEventKind, PttState, PttTurnMachine


def test_double_backtick_starts_turn():
    m = PttTurnMachine(double_window_ms=400)
    e1 = m.on_backtick(1000)
    assert e1.kind == PttEventKind.NOOP
    assert e1.state == PttState.PENDING_START

    e2 = m.on_backtick(1200)  # within window
    assert e2.kind == PttEventKind.TURN_STARTED
    assert e2.state == PttState.LISTENING
    assert m.is_listening


def test_single_backtick_ends_turn_and_yields_utterance():
    m = PttTurnMachine(double_window_ms=400)
    m.on_backtick(0)
    m.on_backtick(50)
    assert m.state == PttState.LISTENING
    m.set_utterance(b"pcm-audio")

    end = m.on_backtick(5000)
    assert end.kind == PttEventKind.TURN_ENDED
    assert end.state == PttState.IDLE
    assert end.utterance == b"pcm-audio"
    assert not m.is_listening


def test_lone_backtick_while_idle_does_not_start():
    m = PttTurnMachine(double_window_ms=300)
    e1 = m.on_backtick(0)
    assert e1.state == PttState.PENDING_START
    # Expire the pending first tap.
    tick = m.on_tick(400)
    assert tick.kind == PttEventKind.NOOP
    assert tick.state == PttState.IDLE
    assert not m.is_listening


def test_double_backtick_does_not_end_turn():
    """While idle, `` starts; it never ends a non-listening turn."""
    m = PttTurnMachine(double_window_ms=400)
    m.on_backtick(0)
    started = m.on_backtick(100)
    assert started.kind == PttEventKind.TURN_STARTED
    # Still listening — second pair is not an end until a single ` later.
    assert m.state == PttState.LISTENING


def test_single_backtick_while_listening_ends_not_double_required():
    m = PttTurnMachine(double_window_ms=400)
    m.on_backtick(0)
    m.on_backtick(10)
    ended = m.on_backtick(9999)
    assert ended.kind == PttEventKind.TURN_ENDED
    assert ended.state == PttState.IDLE


def test_late_second_tap_does_not_count_as_double():
    m = PttTurnMachine(double_window_ms=200)
    m.on_backtick(0)
    # Simulate window expiry then a new first tap semantics via on_backtick past window.
    m.on_tick(250)
    assert m.state == PttState.IDLE
    # Now a single late press only goes pending, does not start.
    e = m.on_backtick(300)
    assert e.kind == PttEventKind.NOOP
    assert e.state == PttState.PENDING_START
