"""xAI Grok Voice Think Fast 2.0 realtime WebSocket client."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import sys
from typing import Any, Callable, Optional

from .config import SYSTEM_INSTRUCTIONS, VoiceConfig
from .herdr_control import HerdrController
from .tools import HERDR_TOOLS

logger = logging.getLogger(__name__)

ToolHandler = Callable[[str, dict[str, Any]], Any]


def reconnect_backoff_s(attempt: int, cap_s: float = 30.0) -> float:
    """Exponential backoff seconds: 1, 2, 4, ... capped (attempt is 0-based)."""
    if attempt < 0:
        attempt = 0
    delay = float(2**attempt)
    return min(delay, cap_s)


class GrokVoiceClient:
    """Speech-to-speech client with manual PTT turn-taking and herdr tools.

    Turn detection is disabled server-side (`turn_detection: null`). The host
    appends mic audio while listening, then commits + response.create on end.
    Auto-reconnects with xAI session resumption when enabled on VoiceConfig.
    """

    def __init__(
        self,
        config: VoiceConfig,
        api_key: str,
        controller: HerdrController,
        *,
        on_audio_out: Optional[Callable[[bytes], None]] = None,
        on_event: Optional[Callable[[dict[str, Any]], None]] = None,
        on_connection_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.config = config
        self.api_key = api_key
        self.controller = controller
        self.on_audio_out = on_audio_out
        self.on_event = on_event
        self.on_connection_change = on_connection_change
        self._ws: Any = None
        self._recv_task: Optional[asyncio.Task[None]] = None
        self._watch_task: Optional[asyncio.Task[None]] = None
        self._pending_function_calls: list[dict[str, Any]] = []
        self._connected = asyncio.Event()
        self._closing = False
        self.conversation_id: Optional[str] = None
        self._reconnect_attempt = 0

    @property
    def url(self) -> str:
        return self.config.realtime_url(self.conversation_id)

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and self._connected.is_set()

    def session_update_payload(self) -> dict[str, Any]:
        return {
            "type": "session.update",
            "session": {
                "voice": self.config.voice,
                "instructions": SYSTEM_INSTRUCTIONS,
                "turn_detection": None,  # manual PTT via `` / `
                "tools": HERDR_TOOLS,
                "resumption": {"enabled": True},
                "audio": {
                    "input": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": self.config.sample_rate,
                        }
                    },
                    "output": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": self.config.sample_rate,
                        }
                    },
                },
            },
        }

    def _notify(self, status: str) -> None:
        msg = f"herdr-voice: {status}"
        print(msg, flush=True)
        logger.info(status)
        if self.on_connection_change:
            try:
                self.on_connection_change(status)
            except Exception:
                logger.exception("on_connection_change failed")

    async def connect(self) -> None:
        """Open the realtime socket, apply session.update, start reconnect watcher."""
        await self._open_socket()
        if self.config.reconnect_enabled and (
            self._watch_task is None or self._watch_task.done()
        ):
            self._watch_task = asyncio.create_task(self._watch_connection())

    async def _open_socket(self) -> None:
        try:
            import websockets
        except ImportError as exc:
            raise SystemExit(
                "Missing dependency 'websockets'. Install voice requirements:\n"
                "  pip install -r voice/requirements.txt"
            ) from exc

        await self._close_socket_only()
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            self._ws = await websockets.connect(
                self.url,
                additional_headers=headers,
                max_size=16 * 1024 * 1024,
            )
        except TypeError:
            self._ws = await websockets.connect(
                self.url,
                extra_headers=headers,
                max_size=16 * 1024 * 1024,
            )
        await self._ws.send(json.dumps(self.session_update_payload()))
        self._recv_task = asyncio.create_task(self._recv_loop())
        self._connected.set()
        self._reconnect_attempt = 0
        logger.info("Connected to %s", self.url)

    async def close(self) -> None:
        self._closing = True
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
            self._watch_task = None
        await self._close_socket_only()
        self._connected.clear()

    async def _close_socket_only(self) -> None:
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
            self._recv_task = None
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                logger.debug("ws close error", exc_info=True)
            self._ws = None
        self._connected.clear()

    async def _watch_connection(self) -> None:
        """Reconnect when the receive loop exits unexpectedly."""
        while not self._closing and self.config.reconnect_enabled:
            task = self._recv_task
            if task is not None:
                try:
                    await task
                except asyncio.CancelledError:
                    if self._closing:
                        raise
                if self._closing:
                    return
                # Recv loop ended without close() — fall through to reconnect.
                self._connected.clear()
                self._ws = None
                self._recv_task = None
            elif self.is_connected:
                await asyncio.sleep(0.2)
                continue
            # Need reconnect (dead socket or failed previous attempt).
            delay = reconnect_backoff_s(
                self._reconnect_attempt, self.config.reconnect_cap_s
            )
            self._reconnect_attempt += 1
            self._notify(
                f"reconnecting… (attempt {self._reconnect_attempt}, wait {delay:.0f}s)"
            )
            await asyncio.sleep(delay)
            if self._closing:
                return
            try:
                # Open socket without nesting another watch task.
                await self._open_socket()
                self._notify("reconnected")
            except Exception:
                logger.exception("Reconnect failed")

    async def append_audio(self, pcm16_le: bytes) -> None:
        if not self._ws:
            return
        payload = {
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(pcm16_le).decode("ascii"),
        }
        try:
            await self._ws.send(json.dumps(payload))
        except Exception:
            logger.warning("append_audio failed (socket dead?)", exc_info=True)

    async def commit_and_respond(self) -> None:
        """End-of-turn: commit buffered audio and request a model response."""
        if not self._ws:
            logger.error("commit_and_respond: not connected")
            print("herdr-voice: not connected — wait for reconnect", file=sys.stderr)
            return
        try:
            await self._ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
            await self._ws.send(json.dumps({"type": "response.create"}))
        except Exception:
            logger.exception("commit_and_respond failed")

    async def clear_input_buffer(self) -> None:
        if not self._ws:
            return
        try:
            await self._ws.send(json.dumps({"type": "input_audio_buffer.clear"}))
        except Exception:
            logger.warning("clear_input_buffer failed", exc_info=True)

    async def _recv_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                if isinstance(raw, bytes):
                    if self.on_audio_out:
                        self.on_audio_out(raw)
                    continue
                event = json.loads(raw)
                if self.on_event:
                    self.on_event(event)
                await self._handle_event(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Grok receive loop error")

    async def _handle_event(self, event: dict[str, Any]) -> None:
        etype = event.get("type", "")
        if etype == "conversation.created":
            conv = event.get("conversation") or {}
            cid = conv.get("id") or event.get("id")
            if cid:
                self.conversation_id = str(cid)
                logger.info("conversation_id=%s", self.conversation_id)
            return

        if etype in ("response.output_audio.delta", "response.audio.delta"):
            delta = event.get("delta") or event.get("audio")
            if delta and self.on_audio_out:
                self.on_audio_out(base64.b64decode(delta))
            return

        if etype == "response.function_call_arguments.done":
            self._pending_function_calls.append(event)
            return

        if etype == "response.done":
            calls = list(self._pending_function_calls)
            self._pending_function_calls.clear()
            if not calls:
                return
            for call in calls:
                await self._run_function_call(call)
            # After all tool outputs, continue the agent turn.
            if self._ws:
                try:
                    await self._ws.send(json.dumps({"type": "response.create"}))
                except Exception:
                    logger.exception("response.create after tools failed")

    async def _run_function_call(self, event: dict[str, Any]) -> None:
        name = event.get("name") or ""
        call_id = event.get("call_id") or ""
        raw_args = event.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
        except json.JSONDecodeError:
            arguments = {}
        logger.info("Tool call %s(%s)", name, arguments)
        try:
            # Run blocking CLI off the event loop so timeouts don't freeze audio.
            result = await asyncio.to_thread(
                self.controller.execute_intent, name, arguments
            )
            output = {
                "argv": result.argv,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
            if result.returncode == -1 and "error=timeout" in (result.stderr or ""):
                output["error"] = "timeout"
        except Exception as exc:
            output = {"error": str(exc)}
        if self._ws:
            try:
                await self._ws.send(
                    json.dumps(
                        {
                            "type": "conversation.item.create",
                            "item": {
                                "type": "function_call_output",
                                "call_id": call_id,
                                "output": json.dumps(output),
                            },
                        }
                    )
                )
            except Exception:
                logger.exception("failed to send function_call_output")


async def wait_closed(client: GrokVoiceClient) -> None:
    if client._recv_task:
        await client._recv_task
