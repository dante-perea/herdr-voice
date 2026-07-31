"""Grok realtime function-tool schemas for herdr control."""

from __future__ import annotations

from typing import Any

# OpenAI/xAI realtime-compatible function tool definitions.
HERDR_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "session_snapshot",
        "description": (
            "Read full herdr session context: status, sessions, workspaces (spaces), "
            "tabs, panes, and agents. Call this when you need IDs or current layout."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "type": "function",
        "name": "workspace_list",
        "description": "List workspaces (spaces) in the active herdr session.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "type": "function",
        "name": "workspace_create",
        "description": "Create a new workspace (space). Returns workspace/tab/pane IDs.",
        "parameters": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Human label for the space"},
                "cwd": {"type": "string", "description": "Working directory path"},
                "focus": {"type": "boolean", "description": "Focus the new workspace"},
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "workspace_focus",
        "description": "Focus a workspace by id.",
        "parameters": {
            "type": "object",
            "properties": {"workspace_id": {"type": "string"}},
            "required": ["workspace_id"],
        },
    },
    {
        "type": "function",
        "name": "workspace_close",
        "description": "Close a workspace by id.",
        "parameters": {
            "type": "object",
            "properties": {"workspace_id": {"type": "string"}},
            "required": ["workspace_id"],
        },
    },
    {
        "type": "function",
        "name": "workspace_rename",
        "description": "Rename a workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "workspace_id": {"type": "string"},
                "label": {"type": "string"},
            },
            "required": ["workspace_id", "label"],
        },
    },
    {
        "type": "function",
        "name": "tab_list",
        "description": "List tabs, optionally filtered by workspace.",
        "parameters": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "tab_create",
        "description": "Create a tab in a workspace (active workspace if omitted).",
        "parameters": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
                "label": {"type": "string"},
                "cwd": {"type": "string"},
                "focus": {"type": "boolean"},
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "tab_focus",
        "description": "Focus a tab by id.",
        "parameters": {
            "type": "object",
            "properties": {"tab_id": {"type": "string"}},
            "required": ["tab_id"],
        },
    },
    {
        "type": "function",
        "name": "tab_close",
        "description": "Close a tab by id.",
        "parameters": {
            "type": "object",
            "properties": {"tab_id": {"type": "string"}},
            "required": ["tab_id"],
        },
    },
    {
        "type": "function",
        "name": "pane_list",
        "description": "List panes.",
        "parameters": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "pane_split",
        "description": "Split a pane right or down.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["right", "down"]},
                "pane_id": {"type": "string"},
                "cwd": {"type": "string"},
                "focus": {"type": "boolean"},
                "ratio": {"type": "number"},
            },
            "required": [],
        },
    },
    {
        "type": "function",
        "name": "pane_close",
        "description": "Close a pane.",
        "parameters": {
            "type": "object",
            "properties": {"pane_id": {"type": "string"}},
            "required": ["pane_id"],
        },
    },
    {
        "type": "function",
        "name": "pane_focus",
        "description": "Focus a neighboring pane by direction.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["left", "right", "up", "down"],
                },
                "pane_id": {"type": "string"},
            },
            "required": ["direction"],
        },
    },
    {
        "type": "function",
        "name": "pane_read",
        "description": "Read terminal output from a pane.",
        "parameters": {
            "type": "object",
            "properties": {
                "pane_id": {"type": "string"},
                "source": {
                    "type": "string",
                    "enum": ["visible", "recent", "recent-unwrapped", "detection"],
                },
                "lines": {"type": "integer"},
            },
            "required": ["pane_id"],
        },
    },
    {
        "type": "function",
        "name": "pane_send_text",
        "description": "Send text to a pane without submitting Enter.",
        "parameters": {
            "type": "object",
            "properties": {
                "pane_id": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["pane_id", "text"],
        },
    },
    {
        "type": "function",
        "name": "pane_run",
        "description": "Run a shell command in a pane (text + Enter).",
        "parameters": {
            "type": "object",
            "properties": {
                "pane_id": {"type": "string"},
                "command": {"type": "string"},
            },
            "required": ["pane_id", "command"],
        },
    },
    {
        "type": "function",
        "name": "agent_list",
        "description": "List live agents.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "type": "function",
        "name": "agent_start",
        "description": (
            "Start a named interactive agent in an existing free shell pane. "
            "Kinds include: claude, codex, gemini, cursor, grok, opencode, copilot, etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Unique live agent name: [a-z][a-z0-9_-]{0,31}",
                },
                "kind": {"type": "string"},
                "pane_id": {"type": "string"},
                "timeout_ms": {"type": "integer"},
                "agent_args": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["name", "kind", "pane_id"],
        },
    },
    {
        "type": "function",
        "name": "agent_prompt",
        "description": "Send a prompt to an agent (atomic paste + Enter).",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Agent name or pane id"},
                "text": {"type": "string"},
                "wait": {"type": "boolean"},
                "timeout_ms": {"type": "integer"},
            },
            "required": ["target", "text"],
        },
    },
    {
        "type": "function",
        "name": "agent_focus",
        "description": "Focus an agent target.",
        "parameters": {
            "type": "object",
            "properties": {"target": {"type": "string"}},
            "required": ["target"],
        },
    },
    {
        "type": "function",
        "name": "agent_wait",
        "description": "Wait until an agent settles (idle/done/blocked).",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "timeout_ms": {"type": "integer"},
            },
            "required": ["target"],
        },
    },
    {
        "type": "function",
        "name": "agent_attach",
        "description": "Attach to an agent terminal session.",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "takeover": {"type": "boolean"},
            },
            "required": ["target"],
        },
    },
    {
        "type": "function",
        "name": "agent_read",
        "description": "Read an agent's terminal output.",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "source": {"type": "string"},
                "lines": {"type": "integer"},
            },
            "required": ["target"],
        },
    },
]


def tool_names() -> list[str]:
    return [t["name"] for t in HERDR_TOOLS]
