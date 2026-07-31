"""Herdr Voice: Grok Voice Think Fast 2.0 hands-free controller for herdr."""

__version__ = "0.1.0"

from .config import DEFAULT_MODEL_ID, XAI_REALTIME_URL
from .ptt import PttEvent, PttState, PttTurnMachine

__all__ = [
    "DEFAULT_MODEL_ID",
    "XAI_REALTIME_URL",
    "PttEvent",
    "PttState",
    "PttTurnMachine",
    "__version__",
]
