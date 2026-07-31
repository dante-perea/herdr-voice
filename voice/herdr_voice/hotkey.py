"""Global backtick hotkey bridge into the PTT turn machine."""

from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Callable, Optional

from .ptt import PttEvent, PttEventKind, PttTurnMachine

logger = logging.getLogger(__name__)

# pynput key for backtick / grave accent.
BACKTICK_CHARS = {"`", "dead_grave", "grave"}


class BacktickHotkeyListener:
    """Listens for global backtick presses and feeds PttTurnMachine.

    `` (two presses within the double window) → TURN_STARTED
    ` while listening → TURN_ENDED
    lone ` while idle → NOOP after window expires
    """

    def __init__(
        self,
        machine: PttTurnMachine,
        on_event: Callable[[PttEvent], None],
        *,
        tick_ms: int = 50,
        on_fatal: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.machine = machine
        self.on_event = on_event
        self.tick_ms = tick_ms
        self.on_fatal = on_fatal
        self._listener = None
        self._tick_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.healthy: bool = False

    def start(self) -> None:
        try:
            from pynput import keyboard
        except ImportError as exc:
            raise SystemExit(
                "Missing dependency 'pynput' for global hotkeys.\n"
                "  pip install -r voice/requirements.txt"
            ) from exc

        def on_press(key) -> None:  # type: ignore[no-untyped-def]
            if not self._is_backtick(key):
                return
            now_ms = int(time.time() * 1000)
            event = self.machine.on_backtick(now_ms)
            if event.kind != PttEventKind.NOOP or event.state.name == "PENDING_START":
                logger.debug("PTT event: %s state=%s", event.kind, event.state)
            try:
                self.on_event(event)
            except Exception:
                logger.exception("PTT event handler failed")

        self._listener = keyboard.Listener(on_press=on_press)
        self._listener.start()
        self.healthy = True
        self._stop.clear()
        self._tick_thread = threading.Thread(target=self._tick_loop, name="ptt-tick", daemon=True)
        self._tick_thread.start()
        logger.info(
            "Hotkeys armed: press `` (double backtick) to talk, ` (single) to end turn"
        )

    def _fatal(self, reason: str) -> None:
        self.healthy = False
        msg = f"hotkeys dead: {reason}"
        logger.error(msg)
        print(f"herdr-voice: ERROR {msg}", file=sys.stderr, flush=True)
        if self.on_fatal:
            try:
                self.on_fatal(reason)
            except Exception:
                logger.exception("on_fatal failed")


    def stop(self) -> None:
        self._stop.set()
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        if self._tick_thread and self._tick_thread.is_alive():
            self._tick_thread.join(timeout=1.0)
        self._tick_thread = None

    def _tick_loop(self) -> None:
        while not self._stop.wait(self.tick_ms / 1000.0):
            # pynput listener thread died → fail closed for the process.
            if self._listener is not None and not getattr(self._listener, "running", True):
                self._fatal("pynput listener stopped")
                return
            now_ms = int(time.time() * 1000)
            prev = self.machine.state
            event = self.machine.on_tick(now_ms)
            if prev != event.state:
                try:
                    self.on_event(event)
                except Exception:
                    logger.exception("PTT tick handler failed")

    @staticmethod
    def _is_backtick(key) -> bool:  # type: ignore[no-untyped-def]
        try:
            from pynput.keyboard import KeyCode
        except ImportError:
            return False
        if isinstance(key, KeyCode):
            if key.char in ("`", "´"):
                return True
            # Some layouts report vk for OEM_3 (US backtick)
            if getattr(key, "vk", None) in (192, 0xC0):
                return True
        # Named keys if present
        name = getattr(key, "name", None)
        if name and name.lower() in BACKTICK_CHARS:
            return True
        return False
