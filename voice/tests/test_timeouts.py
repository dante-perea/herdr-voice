"""CLI hard-timeout behavior (stability pillar 1)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herdr_voice.herdr_control import CommandResult, HerdrController


def test_timeout_for_ordinary_intent_uses_default():
    c = HerdrController(default_timeout_s=30, long_timeout_s=120)
    assert c.timeout_for_intent("workspace_list", {}) == 30.0
    assert c.timeout_for_intent("tab_create", {"label": "x"}) == 30.0


def test_timeout_for_long_intent_uses_long_default():
    c = HerdrController(default_timeout_s=30, long_timeout_s=120)
    assert c.timeout_for_intent("agent_wait", {}) == 120.0
    assert c.timeout_for_intent("pane_run", {"pane_id": "p1", "command": "x"}) == 120.0


def test_timeout_ms_arg_overrides_defaults():
    c = HerdrController(default_timeout_s=30, long_timeout_s=120)
    assert c.timeout_for_intent("agent_wait", {"timeout_ms": 5000}) == 5.0
    assert c.timeout_for_intent("workspace_list", {"timeout_ms": 1500}) == 1.5


def test_run_timeout_returns_structured_error(monkeypatch: pytest.MonkeyPatch):
    def boom(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd=["herdr", "status"], timeout=0.01)

    monkeypatch.setattr(subprocess, "run", boom)
    c = HerdrController(default_timeout_s=0.01)
    result = c.run(["herdr", "status"])
    assert result.returncode == -1
    assert "error=timeout" in result.stderr
    assert "timeout_s=" in result.stderr


def test_execute_intent_timeout_propagates(monkeypatch: pytest.MonkeyPatch):
    def boom(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd=["herdr"], timeout=1)

    monkeypatch.setattr(subprocess, "run", boom)
    c = HerdrController(default_timeout_s=1)
    result = c.execute_intent("workspace_list", {})
    assert result.returncode == -1
    assert "error=timeout" in result.stderr
