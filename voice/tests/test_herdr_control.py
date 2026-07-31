"""Unit tests for shipped herdr control argv builders and intent dispatch."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herdr_voice.herdr_control import CommandResult, HerdrController, build_argv
from herdr_voice.tools import HERDR_TOOLS, tool_names


def test_workspace_create_argv():
    c = HerdrController(herdr_bin="herdr")
    argv = c.workspace_create(label="api", cwd="C:/proj", focus=True)
    assert argv == [
        "herdr",
        "workspace",
        "create",
        "--cwd",
        "C:/proj",
        "--label",
        "api",
        "--focus",
    ]


def test_tab_create_argv():
    c = HerdrController(herdr_bin="herdr")
    argv = c.tab_create(workspace="w1", label="tests", focus=False)
    assert argv == [
        "herdr",
        "tab",
        "create",
        "--workspace",
        "w1",
        "--label",
        "tests",
        "--no-focus",
    ]


def test_agent_start_argv():
    c = HerdrController(herdr_bin="herdr")
    argv = c.agent_start(
        "coder",
        kind="claude",
        pane_id="w1:t1:p1",
        timeout_ms=30000,
        agent_args=["--model", "opus"],
    )
    assert argv == [
        "herdr",
        "agent",
        "start",
        "coder",
        "--kind",
        "claude",
        "--pane",
        "w1:t1:p1",
        "--timeout",
        "30000",
        "--",
        "--model",
        "opus",
    ]


def test_session_snapshot_composite_argv():
    c = HerdrController(herdr_bin="herdr")
    vectors = c.session_snapshot()
    assert len(vectors) >= 4
    assert vectors[0] == ["herdr", "status"]
    assert ["herdr", "workspace", "list"] in vectors
    assert ["herdr", "tab", "list"] in vectors
    assert ["herdr", "pane", "list"] in vectors
    assert ["herdr", "agent", "list"] in vectors


def test_build_argv_drives_shipped_builders():
    c = HerdrController(herdr_bin="/opt/herdr")
    argv = build_argv(
        c,
        "workspace_create",
        {"label": "space-a", "cwd": "/tmp/x", "focus": False},
    )
    assert argv[0] == "/opt/herdr"
    assert argv[1:3] == ["workspace", "create"]
    assert "--label" in argv and "space-a" in argv
    assert "--cwd" in argv and "/tmp/x" in argv
    assert "--no-focus" in argv


def test_execute_intent_uses_runner_with_real_argv():
    seen: list[list[str]] = []

    def runner(argv):
        seen.append(list(argv))
        return CommandResult(argv=list(argv), returncode=0, stdout='{"ok":true}', stderr="")

    c = HerdrController(herdr_bin="herdr", runner=runner)
    result = c.execute_intent(
        "tab_create",
        {"workspace": "w1", "label": "voice", "focus": True},
    )
    assert result.returncode == 0
    assert seen == [
        ["herdr", "tab", "create", "--workspace", "w1", "--label", "voice", "--focus"]
    ]
    assert result.argv == seen[0]


def test_execute_session_snapshot_runs_composite():
    seen: list[list[str]] = []

    def runner(argv):
        seen.append(list(argv))
        return CommandResult(argv=list(argv), returncode=0, stdout="{}", stderr="")

    c = HerdrController(herdr_bin="herdr", runner=runner)
    result = c.execute_intent("session_snapshot", {})
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "snapshot" in payload
    assert any(a[1:3] == ["workspace", "list"] for a in seen)
    assert any(a[1:3] == ["agent", "list"] for a in seen)
    assert any(a[1:3] == ["tab", "list"] for a in seen)


def test_agent_prompt_and_pane_split_argv():
    c = HerdrController()
    assert c.agent_prompt("coder", "hello", wait=True, timeout_ms=5000) == [
        "herdr",
        "agent",
        "prompt",
        "coder",
        "hello",
        "--wait",
        "--timeout",
        "5000",
    ]
    assert c.pane_split(direction="down", pane_id="w1:t1:p2", focus=True) == [
        "herdr",
        "pane",
        "split",
        "w1:t1:p2",
        "--direction",
        "down",
        "--focus",
    ]


def test_tools_include_core_control_surface():
    names = set(tool_names())
    for required in (
        "workspace_create",
        "tab_create",
        "agent_start",
        "session_snapshot",
        "pane_split",
        "agent_prompt",
    ):
        assert required in names
    # Schemas are realtime function tools.
    assert all(t["type"] == "function" for t in HERDR_TOOLS)
