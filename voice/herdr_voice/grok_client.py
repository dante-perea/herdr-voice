"""xAI Grok Voice Think Fast 2.0 realtime WebSocket client."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, Awaitable, Callable, Optional

from .config import SYSTEM_INSTRUCTIONS, VoiceConfig
from .herdr_control import HerdrController
from .tools import HERDR_TOOLS

logger = logging.getLogger(__name__)

ToolHandler = Callable[[str, dict[str, Any]], Any]


class GrokVoiceClient:
    """Speech-to-speech client with manual PTT turn-taking and herdr tools.

    Turn detection is disabled server-side (`turn_detection: null`). The host
    appends mic audio while listening, then commits + response.create on end.
    """

    def __init__(
        self,
        config: VoiceConfig,
        api_key: str,
        controller: HerdrController,
        *,
        on_audio_out: Optional[Callable[[bytes], None]] = None,
        on_event: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> None:
        self.config = config
        self.api_key = api_key
        self.controller = controller
        self.on_audio_out = on_audio_out
        self.on_event = on_event
        self._ws: Any = None
        self._recv_task: Optional[asyncio.Task[None]] = None
        self._pending_function_calls: list[dict[str, Any]] = []
        self._connected = asyncio.Event()

    @property
    def url(self) -> str:
        return self.config.realtime_url()

    def session_update_payload(self) -> dict[str, Any]:
        return {
            "type": "session.update",
            "session": {
                "voice": self.config.voice,
                "instructions": SYSTEM_INSTRUCTIONS,
                "turn_detection": None,  # manual PTT via `` / `
                "tools": HERDR_TOOLS,
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

    async def connect(self) -> None:
        try:
            import websockets
        except ImportError as exc:
            raise SystemExit(
                "Missing dependency 'websockets'. Install voice requirements:\n"
                "  pip install -r voice/requirements.txt"
            ) from exc

        headers = {"Authorization": f"Bearer {self.api_key}"}
        # websockets API differs slightly across majors.
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
        logger.info("Connected to %s", self.url)

    async def close(self) -> None:
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
            self._recv_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        self._connected.clear()

    async def append_audio(self, pcm16_le: bytes) -> None:
        if not self._ws:
            return
        payload = {
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(pcm16_le).decode("ascii"),
        }
        await self._ws.send(json.dumps(payload))

    async def commit_and_respond(self) -> None:
        """End-of-turn: commit buffered audio and request a model response."""
        if not self._ws:
            return
        await self._ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        await self._ws.send(json.dumps({"type": "response.create"}))

    async def clear_input_buffer(self) -> None:
        if not self._ws:
            return
        await self._ws.send(json.dumps({"type": "input_audio_buffer.clear"}))

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
                await self._ws.send(json.dumps({"type": "response.create"}))

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
            result = self.controller.execute_intent(name, arguments)
            output = {
                "argv": result.argv,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as exc:
            output = {"error": str(exc)}
        if self._ws:
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


async def wait_closed(client: GrokVoiceClient) -> None:
    if client._recv_task:
        await client._recv_task
