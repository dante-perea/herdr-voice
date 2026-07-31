#!/usr/bin/env python3
"""Automated stability smoke for herdr-voice (no human PTT required).

Exit 0 only if all automated checks pass.
Requires: XAI_API_KEY, running herdr server (for CLI tool path), network.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from herdr_voice.config import VoiceConfig
from herdr_voice.grok_client import GrokVoiceClient, reconnect_backoff_s
from herdr_voice.herdr_control import HerdrController


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check_pytest() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        _fail(f"pytest failed\n{r.stdout}\n{r.stderr}")
    print("OK pytest")


def check_timeout() -> None:
    import logging

    c = HerdrController(herdr_bin=sys.executable, default_timeout_s=0.4)
    t0 = time.monotonic()
    logging.disable(logging.ERROR)
    try:
        result = c.run(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            timeout_s=0.4,
        )
    finally:
        logging.disable(logging.NOTSET)
    elapsed = time.monotonic() - t0
    if result.returncode != -1 or "error=timeout" not in result.stderr:
        _fail(f"timeout path broken: {result}")
    if elapsed > 5:
        _fail(f"timeout took too long: {elapsed:.1f}s")
    print(f"OK timeout ({elapsed:.2f}s)")

def check_backoff() -> None:
    assert reconnect_backoff_s(0) == 1
    assert reconnect_backoff_s(10, cap_s=30) == 30
    print("OK backoff")


async def check_ws_and_herdr() -> None:
    cfg = VoiceConfig.from_env()
    if not os.environ.get(cfg.api_key_env, "").strip():
        _fail(f"missing {cfg.api_key_env}")
    herdr = os.environ.get("HERDR_BIN", cfg.herdr_bin)
    key = cfg.require_api_key()
    events: list[str] = []
    client = GrokVoiceClient(
        cfg,
        key,
        HerdrController(
            herdr_bin=herdr,
            default_timeout_s=cfg.cli_timeout_s,
            long_timeout_s=cfg.cli_long_timeout_s,
        ),
        on_event=lambda e: events.append(str(e.get("type"))),
    )
    try:
        await asyncio.wait_for(client.connect(), timeout=45)
        await asyncio.sleep(2)
        if not client.is_connected:
            _fail("ws not connected")
        if "session.created" not in events and "conversation.created" not in events:
            _fail(f"missing bootstrap events: {events}")
        if not client.session_update_payload()["session"].get("resumption", {}).get(
            "enabled"
        ):
            _fail("resumption not enabled")
        result = await asyncio.to_thread(
            client.controller.execute_intent, "workspace_list", {}
        )
        if result.returncode != 0:
            _fail(f"workspace_list rc={result.returncode} stderr={result.stderr}")
        print(
            f"OK ws+herdr conversation_id={client.conversation_id!r} "
            f"events={events[:8]}"
        )
    finally:
        await client.close()


def main() -> int:
    print("herdr-voice automated stability smoke")
    check_backoff()
    check_timeout()
    check_pytest()
    asyncio.run(check_ws_and_herdr())
    print("ALL_SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
