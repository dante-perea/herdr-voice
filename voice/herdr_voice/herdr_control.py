"""Build real herdr CLI argv payloads for automation control.

These functions construct the exact argv that would be executed against the
herdr binary (CLI surface documented at herdr.dev). Execution is optional and
injectable so unit tests can assert payloads without a live server.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence


Runner = Callable[[Sequence[str]], "CommandResult"]


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        text = self.stdout.strip()
        if not text:
            return None
        return json.loads(text)


@dataclass
class HerdrController:
    """Maps high-level intents to herdr CLI argv and optional execution."""

    herdr_bin: str = "herdr"
    runner: Optional[Runner] = None
    env: Optional[Mapping[str, str]] = None
    # Last argv produced (even without running) — useful for inspection.
    last_argv: list[str] = field(default_factory=list)

    # --- argv builders (pure; unit-test target) ---

    def _base(self, *parts: str) -> list[str]:
        argv = [self.herdr_bin, *parts]
        self.last_argv = list(argv)
        return argv

    def workspace_list(self) -> list[str]:
        return self._base("workspace", "list")

    def workspace_create(
        self,
        *,
        cwd: Optional[str] = None,
        label: Optional[str] = None,
        focus: Optional[bool] = None,
        env: Optional[Sequence[str]] = None,
    ) -> list[str]:
        argv = self._base("workspace", "create")
        if cwd:
            argv.extend(["--cwd", cwd])
        if label:
            argv.extend(["--label", label])
        if focus is True:
            argv.append("--focus")
        elif focus is False:
            argv.append("--no-focus")
        if env:
            for item in env:
                argv.extend(["--env", item])
        self.last_argv = list(argv)
        return argv

    def workspace_focus(self, workspace_id: str) -> list[str]:
        return self._base("workspace", "focus", workspace_id)

    def workspace_close(self, workspace_id: str) -> list[str]:
        return self._base("workspace", "close", workspace_id)

    def workspace_rename(self, workspace_id: str, label: str) -> list[str]:
        return self._base("workspace", "rename", workspace_id, label)

    def tab_list(self, *, workspace: Optional[str] = None) -> list[str]:
        argv = self._base("tab", "list")
        if workspace:
            argv.extend(["--workspace", workspace])
        self.last_argv = list(argv)
        return argv

    def tab_create(
        self,
        *,
        workspace: Optional[str] = None,
        cwd: Optional[str] = None,
        label: Optional[str] = None,
        focus: Optional[bool] = None,
        env: Optional[Sequence[str]] = None,
    ) -> list[str]:
        argv = self._base("tab", "create")
        if workspace:
            argv.extend(["--workspace", workspace])
        if cwd:
            argv.extend(["--cwd", cwd])
        if label:
            argv.extend(["--label", label])
        if focus is True:
            argv.append("--focus")
        elif focus is False:
            argv.append("--no-focus")
        if env:
            for item in env:
                argv.extend(["--env", item])
        self.last_argv = list(argv)
        return argv

    def tab_focus(self, tab_id: str) -> list[str]:
        return self._base("tab", "focus", tab_id)

    def tab_close(self, tab_id: str) -> list[str]:
        return self._base("tab", "close", tab_id)

    def tab_rename(self, tab_id: str, label: str) -> list[str]:
        return self._base("tab", "rename", tab_id, label)

    def pane_list(self, *, workspace: Optional[str] = None) -> list[str]:
        argv = self._base("pane", "list")
        if workspace:
            argv.extend(["--workspace", workspace])
        self.last_argv = list(argv)
        return argv

    def pane_split(
        self,
        *,
        direction: str = "right",
        pane_id: Optional[str] = None,
        cwd: Optional[str] = None,
        focus: Optional[bool] = None,
        ratio: Optional[float] = None,
    ) -> list[str]:
        argv = self._base("pane", "split")
        if pane_id:
            argv.append(pane_id)
        argv.extend(["--direction", direction])
        if cwd:
            argv.extend(["--cwd", cwd])
        if ratio is not None:
            argv.extend(["--ratio", str(ratio)])
        if focus is True:
            argv.append("--focus")
        elif focus is False:
            argv.append("--no-focus")
        self.last_argv = list(argv)
        return argv

    def pane_close(self, pane_id: str) -> list[str]:
        return self._base("pane", "close", pane_id)

    def pane_focus(self, *, direction: str, pane_id: Optional[str] = None) -> list[str]:
        argv = self._base("pane", "focus", "--direction", direction)
        if pane_id:
            argv.extend(["--pane", pane_id])
        self.last_argv = list(argv)
        return argv

    def pane_read(
        self,
        pane_id: str,
        *,
        source: str = "recent",
        lines: Optional[int] = None,
    ) -> list[str]:
        argv = self._base("pane", "read", pane_id, "--source", source)
        if lines is not None:
            argv.extend(["--lines", str(lines)])
        self.last_argv = list(argv)
        return argv

    def pane_send_text(self, pane_id: str, text: str) -> list[str]:
        return self._base("pane", "send-text", pane_id, text)

    def pane_run(self, pane_id: str, command: str) -> list[str]:
        return self._base("pane", "run", pane_id, command)

    def agent_list(self) -> list[str]:
        return self._base("agent", "list")

    def agent_start(
        self,
        name: str,
        *,
        kind: str,
        pane_id: str,
        timeout_ms: Optional[int] = None,
        agent_args: Optional[Sequence[str]] = None,
    ) -> list[str]:
        argv = self._base(
            "agent",
            "start",
            name,
            "--kind",
            kind,
            "--pane",
            pane_id,
        )
        if timeout_ms is not None:
            argv.extend(["--timeout", str(timeout_ms)])
        if agent_args:
            argv.append("--")
            argv.extend(list(agent_args))
        self.last_argv = list(argv)
        return argv

    def agent_prompt(
        self,
        target: str,
        text: str,
        *,
        wait: bool = False,
        timeout_ms: Optional[int] = None,
    ) -> list[str]:
        argv = self._base("agent", "prompt", target, text)
        if wait:
            argv.append("--wait")
        if timeout_ms is not None:
            argv.extend(["--timeout", str(timeout_ms)])
        self.last_argv = list(argv)
        return argv

    def agent_focus(self, target: str) -> list[str]:
        return self._base("agent", "focus", target)

    def agent_wait(self, target: str, *, timeout_ms: Optional[int] = None) -> list[str]:
        argv = self._base("agent", "wait", target)
        if timeout_ms is not None:
            argv.extend(["--timeout", str(timeout_ms)])
        self.last_argv = list(argv)
        return argv

    def agent_attach(self, target: str, *, takeover: bool = False) -> list[str]:
        argv = self._base("agent", "attach", target)
        if takeover:
            argv.append("--takeover")
        self.last_argv = list(argv)
        return argv

    def agent_read(
        self,
        target: str,
        *,
        source: str = "recent",
        lines: Optional[int] = None,
    ) -> list[str]:
        argv = self._base("agent", "read", target, "--source", source)
        if lines is not None:
            argv.extend(["--lines", str(lines)])
        self.last_argv = list(argv)
        return argv

    def session_list(self) -> list[str]:
        return self._base("session", "list", "--json")

    def status(self) -> list[str]:
        return self._base("status")

    def session_snapshot(self) -> list[list[str]]:
        """Composite snapshot: status + workspaces + tabs + panes + agents.

        Returns the list of argv vectors that constitute a full situational
        read. Callers that only need one payload for a single RPC may use
        `workspace_list` etc.; the voice agent executes this composite.
        """
        return [
            self.status(),
            self.session_list(),
            self.workspace_list(),
            self.tab_list(),
            self.pane_list(),
            self.agent_list(),
        ]

    # --- execution ---

    def run(self, argv: Sequence[str]) -> CommandResult:
        self.last_argv = list(argv)
        if self.runner is not None:
            return self.runner(argv)
        completed = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            env=None if self.env is None else {**dict(self.env)},
            check=False,
        )
        return CommandResult(
            argv=list(argv),
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )

    def execute_intent(self, name: str, arguments: Mapping[str, Any]) -> CommandResult:
        """Dispatch a tool name + JSON args to argv builder + run."""
        argv = build_argv(self, name, arguments)
        if name == "session_snapshot":
            # Composite: run each and merge.
            parts: list[dict[str, Any]] = []
            last: Optional[CommandResult] = None
            for one in self.session_snapshot():
                last = self.run(one)
                parts.append(
                    {
                        "argv": last.argv,
                        "returncode": last.returncode,
                        "stdout": last.stdout,
                        "stderr": last.stderr,
                    }
                )
            assert last is not None
            merged = CommandResult(
                argv=last.argv,
                returncode=max(p["returncode"] for p in parts),
                stdout=json.dumps({"snapshot": parts}),
                stderr="",
            )
            return merged
        return self.run(argv)


def build_argv(
    controller: HerdrController,
    name: str,
    arguments: Mapping[str, Any],
) -> list[str]:
    """Map tool name → argv via the real controller builders (no reimplementation)."""
    args = dict(arguments or {})
    if name == "workspace_list":
        return controller.workspace_list()
    if name == "workspace_create":
        return controller.workspace_create(
            cwd=args.get("cwd"),
            label=args.get("label"),
            focus=args.get("focus"),
            env=args.get("env"),
        )
    if name == "workspace_focus":
        return controller.workspace_focus(str(args["workspace_id"]))
    if name == "workspace_close":
        return controller.workspace_close(str(args["workspace_id"]))
    if name == "workspace_rename":
        return controller.workspace_rename(str(args["workspace_id"]), str(args["label"]))
    if name == "tab_list":
        return controller.tab_list(workspace=args.get("workspace"))
    if name == "tab_create":
        return controller.tab_create(
            workspace=args.get("workspace"),
            cwd=args.get("cwd"),
            label=args.get("label"),
            focus=args.get("focus"),
            env=args.get("env"),
        )
    if name == "tab_focus":
        return controller.tab_focus(str(args["tab_id"]))
    if name == "tab_close":
        return controller.tab_close(str(args["tab_id"]))
    if name == "tab_rename":
        return controller.tab_rename(str(args["tab_id"]), str(args["label"]))
    if name == "pane_list":
        return controller.pane_list(workspace=args.get("workspace"))
    if name == "pane_split":
        return controller.pane_split(
            direction=str(args.get("direction", "right")),
            pane_id=args.get("pane_id"),
            cwd=args.get("cwd"),
            focus=args.get("focus"),
            ratio=args.get("ratio"),
        )
    if name == "pane_close":
        return controller.pane_close(str(args["pane_id"]))
    if name == "pane_focus":
        return controller.pane_focus(
            direction=str(args["direction"]),
            pane_id=args.get("pane_id"),
        )
    if name == "pane_read":
        return controller.pane_read(
            str(args["pane_id"]),
            source=str(args.get("source", "recent")),
            lines=args.get("lines"),
        )
    if name == "pane_send_text":
        return controller.pane_send_text(str(args["pane_id"]), str(args["text"]))
    if name == "pane_run":
        return controller.pane_run(str(args["pane_id"]), str(args["command"]))
    if name == "agent_list":
        return controller.agent_list()
    if name == "agent_start":
        return controller.agent_start(
            str(args["name"]),
            kind=str(args["kind"]),
            pane_id=str(args["pane_id"]),
            timeout_ms=args.get("timeout_ms"),
            agent_args=args.get("agent_args"),
        )
    if name == "agent_prompt":
        return controller.agent_prompt(
            str(args["target"]),
            str(args["text"]),
            wait=bool(args.get("wait", False)),
            timeout_ms=args.get("timeout_ms"),
        )
    if name == "agent_focus":
        return controller.agent_focus(str(args["target"]))
    if name == "agent_wait":
        return controller.agent_wait(str(args["target"]), timeout_ms=args.get("timeout_ms"))
    if name == "agent_attach":
        return controller.agent_attach(str(args["target"]), takeover=bool(args.get("takeover", False)))
    if name == "agent_read":
        return controller.agent_read(
            str(args["target"]),
            source=str(args.get("source", "recent")),
            lines=args.get("lines"),
        )
    if name == "session_list":
        return controller.session_list()
    if name == "session_snapshot":
        # Composite marker — execute_intent handles multi-run.
        return controller.status()
    if name == "status":
        return controller.status()
    raise ValueError(f"unknown herdr tool: {name}")
