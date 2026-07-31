"""Microphone capture and speaker playback helpers (optional at runtime)."""

from __future__ import annotations

import logging
import queue
import sys
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class MicCapture:
    """Streams PCM16 mono frames while `listening` is True."""

    def __init__(
        self,
        sample_rate: int = 24000,
        frame_ms: int = 40,
        on_frame: Optional[Callable[[bytes], None]] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.on_frame = on_frame
        self._listening = False
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._buffer = bytearray()
        self._lock = threading.Lock()
        self.healthy: bool = False
        self.last_error: Optional[str] = None

    @property
    def listening(self) -> bool:
        return self._listening

    def start_listening(self) -> bool:
        """Begin capture. Returns False if mic is known-dead."""
        if self.last_error and not self.healthy and self._thread and not self._thread.is_alive():
            self._banner(f"mic dead: {self.last_error}")
            return False
        with self._lock:
            self._buffer.clear()
            self._listening = True
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="herdr-voice-mic", daemon=True)
            self._thread.start()
        return True

    def stop_listening(self) -> bytes:
        with self._lock:
            self._listening = False
            data = bytes(self._buffer)
            self._buffer.clear()
        return data

    def close(self) -> None:
        self._listening = False
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    @staticmethod
    def _banner(msg: str) -> None:
        logger.error(msg)
        print(f"herdr-voice: ERROR {msg}", file=sys.stderr, flush=True)

    def _run(self) -> None:
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError as exc:
            self.healthy = False
            self.last_error = "sounddevice/numpy not installed"
            self._banner(
                "sounddevice/numpy not installed — mic capture disabled. "
                "pip install -r voice/requirements.txt"
            )
            return

        blocksize = max(1, int(self.sample_rate * self.frame_ms / 1000))

        def callback(indata, frames, time_info, status) -> None:  # type: ignore[no-untyped-def]
            if status:
                logger.debug("mic status: %s", status)
            if not self._listening:
                return
            mono = indata[:, 0] if indata.ndim > 1 else indata
            pcm = (np.clip(mono, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
            with self._lock:
                self._buffer.extend(pcm)
            if self.on_frame:
                self.on_frame(pcm)

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=blocksize,
                callback=callback,
            ):
                self.healthy = True
                self.last_error = None
                while not self._stop.is_set():
                    self._stop.wait(0.1)
        except Exception as exc:
            self.healthy = False
            self.last_error = str(exc)
            self._banner(f"Microphone stream failed: {exc}")
            logger.exception("Microphone stream failed")


class SpeakerPlayback:
    """Queue-based PCM16 playback with one automatic restart attempt."""

    def __init__(self, sample_rate: int = 24000) -> None:
        self.sample_rate = sample_rate
        self._q: queue.Queue[Optional[bytes]] = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.healthy: bool = False
        self.last_error: Optional[str] = None
        self._restart_used = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="herdr-voice-spk", daemon=True)
        self._thread.start()

    def enqueue(self, pcm16_le: bytes) -> None:
        if pcm16_le:
            self._q.put(pcm16_le)

    def close(self) -> None:
        self._stop.set()
        self._q.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    @staticmethod
    def _banner(msg: str) -> None:
        logger.error(msg)
        print(f"herdr-voice: ERROR {msg}", file=sys.stderr, flush=True)

    def _run(self) -> None:
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            self.healthy = False
            self.last_error = "sounddevice/numpy not installed"
            self._banner("sounddevice/numpy not installed — playback disabled")
            return

        try:
            with sd.OutputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
            ) as stream:
                self.healthy = True
                self.last_error = None
                while not self._stop.is_set():
                    try:
                        item = self._q.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if item is None:
                        break
                    audio = np.frombuffer(item, dtype=np.int16).astype(np.float32) / 32768.0
                    stream.write(audio.reshape(-1, 1))
        except Exception as exc:
            self.healthy = False
            self.last_error = str(exc)
            self._banner(f"Speaker stream failed: {exc}")
            logger.exception("Speaker stream failed")
            if not self._restart_used and not self._stop.is_set():
                self._restart_used = True
                logger.warning("Attempting one speaker restart…")
                self._thread = None
                self.start()
