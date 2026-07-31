"""Push-to-talk turn state machine: `` starts, ` ends.

Contract (acceptance criteria):
- Pressing two backticks (``) while idle starts a listen/speak turn.
- Pressing one backtick (`) while listening ends the turn and submits.
- A lone ` while idle does not start a turn (no-op after the double-tap window).
- A lone `` while listening does not specially end — the first ` ends the turn.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PttState(str, Enum):
    IDLE = "idle"
    PENDING_START = "pending_start"
    LISTENING = "listening"


class PttEventKind(str, Enum):
    TURN_STARTED = "turn_started"
    TURN_ENDED = "turn_ended"
    NOOP = "noop"


@dataclass(frozen=True)
class PttEvent:
    kind: PttEventKind
    state: PttState
    # Optional opaque payload for the ended turn (e.g. audio bytes / transcript).
    utterance: Optional[object] = None


class PttTurnMachine:
    """Deterministic PTT machine driven by backtick key events and time.

    Call `on_backtick(now_ms)` for each backtick key press.
    Call `on_tick(now_ms)` periodically (or after sleeps) so a lone backtick
    while idle expires into a no-op without starting a turn.
    """

    def __init__(self, double_window_ms: int = 450) -> None:
        if double_window_ms <= 0:
            raise ValueError("double_window_ms must be positive")
        self.double_window_ms = double_window_ms
        self.state = PttState.IDLE
        self._pending_at_ms: Optional[int] = None
        self._utterance: Optional[object] = None

    @property
    def is_listening(self) -> bool:
        return self.state == PttState.LISTENING

    def set_utterance(self, utterance: object) -> None:
        """Attach payload collected during the active turn (mic buffer, etc.)."""
        self._utterance = utterance

    def on_backtick(self, now_ms: int) -> PttEvent:
        if self.state == PttState.IDLE:
            self.state = PttState.PENDING_START
            self._pending_at_ms = now_ms
            return PttEvent(PttEventKind.NOOP, self.state)

        if self.state == PttState.PENDING_START:
            assert self._pending_at_ms is not None
            delta = now_ms - self._pending_at_ms
            if 0 <= delta <= self.double_window_ms:
                self.state = PttState.LISTENING
                self._pending_at_ms = None
                self._utterance = None
                return PttEvent(PttEventKind.TURN_STARTED, self.state)
            # Window already elapsed conceptually; treat as fresh first tap.
            self.state = PttState.PENDING_START
            self._pending_at_ms = now_ms
            return PttEvent(PttEventKind.NOOP, self.state)

        if self.state == PttState.LISTENING:
            utterance = self._utterance
            self._utterance = None
            self.state = PttState.IDLE
            self._pending_at_ms = None
            return PttEvent(PttEventKind.TURN_ENDED, self.state, utterance=utterance)

        raise RuntimeError(f"unknown state {self.state}")

    def on_tick(self, now_ms: int) -> PttEvent:
        """Expire a pending first backtick so a lone ` never starts a turn."""
        if self.state != PttState.PENDING_START or self._pending_at_ms is None:
            return PttEvent(PttEventKind.NOOP, self.state)
        if now_ms - self._pending_at_ms > self.double_window_ms:
            self.state = PttState.IDLE
            self._pending_at_ms = None
            return PttEvent(PttEventKind.NOOP, self.state)
        return PttEvent(PttEventKind.NOOP, self.state)

    def force_end(self) -> PttEvent:
        """End a listening turn without a backtick (e.g. process shutdown)."""
        if self.state != PttState.LISTENING:
            self.state = PttState.IDLE
            self._pending_at_ms = None
            return PttEvent(PttEventKind.NOOP, self.state)
        utterance = self._utterance
        self._utterance = None
        self.state = PttState.IDLE
        return PttEvent(PttEventKind.TURN_ENDED, self.state, utterance=utterance)
