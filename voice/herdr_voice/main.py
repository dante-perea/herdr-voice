"""herdr-voice entry point: Grok Voice Think Fast 2.0 + backtick PTT + herdr tools."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import threading
from typing import Optional

from .audio_io import MicCapture, SpeakerPlayback
from .config import DEFAULT_MODEL_ID, VoiceConfig
from .grok_client import GrokVoiceClient
from .herdr_control import HerdrController
from .hotkey import BacktickHotkeyListener
from .ptt import PttEvent, PttEventKind, PttTurnMachine

logger = logging.getLogger("herdr_voice")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="herdr-voice",
        description=(
            "Hands-free herdr controller using Grok Voice Think Fast 2.0. "
            "Press `` to start speaking, ` to end the turn."
        ),
    )
    p.add_argument(
        "--model",
        default=None,
        help=f"xAI voice model id (default: {DEFAULT_MODEL_ID})",
    )
    p.add_argument(
        "--herdr-bin",
        default=None,
        help="Path to herdr executable (default: herdr on PATH)",
    )
    p.add_argument(
        "--voice",
        default=None,
        help="Grok voice id (default: eve)",
    )
    p.add_argument(
        "--dry-run-config",
        action="store_true",
        help="Print resolved config and exit (no network/mic)",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    return p


def _merge_config(base: VoiceConfig, args: argparse.Namespace) -> VoiceConfig:
    return VoiceConfig(
        model_id=args.model or base.model_id,
        api_key_env=base.api_key_env,
        voice=args.voice or base.voice,
        sample_rate=base.sample_rate,
        herdr_bin=args.herdr_bin or base.herdr_bin,
        double_backtick_ms=base.double_backtick_ms,
        cli_timeout_s=base.cli_timeout_s,
        cli_long_timeout_s=base.cli_long_timeout_s,
        reconnect_enabled=base.reconnect_enabled,
        reconnect_cap_s=base.reconnect_cap_s,
    )


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = _merge_config(VoiceConfig.from_env(), args)

    if args.dry_run_config:
        print(f"model_id={config.model_id}")
        print(f"realtime_url={config.realtime_url()}")
        print(f"herdr_bin={config.herdr_bin}")
        print(f"voice={config.voice}")
        print(f"sample_rate={config.sample_rate}")
        print(f"cli_timeout_s={config.cli_timeout_s}")
        print(f"cli_long_timeout_s={config.cli_long_timeout_s}")
        print(f"reconnect_enabled={config.reconnect_enabled}")
        print("ptt=`` start / ` end")
        return 0

    # Fail closed without a key — clear message, not an import crash.
    api_key = config.require_api_key()

    try:
        asyncio.run(run_voice(config, api_key))
    except KeyboardInterrupt:
        print("\nherdr-voice stopped.")
        return 0
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return code
    return 0


async def run_voice(config: VoiceConfig, api_key: str) -> None:
    loop = asyncio.get_running_loop()
    controller = HerdrController(
        herdr_bin=config.herdr_bin,
        default_timeout_s=config.cli_timeout_s,
        long_timeout_s=config.cli_long_timeout_s,
    )
    machine = PttTurnMachine(double_window_ms=config.double_backtick_ms)
    shutdown = asyncio.Event()

    speaker = SpeakerPlayback(sample_rate=config.sample_rate)
    speaker.start()

    client = GrokVoiceClient(
        config,
        api_key,
        controller,
        on_audio_out=lambda pcm: speaker.enqueue(pcm),
        on_event=lambda ev: logger.debug("event %s", ev.get("type")),
    )

    # Mic frames go to the asyncio client when listening.
    def on_mic_frame(pcm: bytes) -> None:
        if not machine.is_listening:
            return
        if not client.is_connected:
            return
        asyncio.run_coroutine_threadsafe(client.append_audio(pcm), loop)

    mic = MicCapture(sample_rate=config.sample_rate, on_frame=on_mic_frame)

    def on_ptt(event: PttEvent) -> None:
        if event.kind == PttEventKind.TURN_STARTED:
            if not client.is_connected:
                logger.error("Not connected — cannot start listen")
                print(
                    "herdr-voice: ERROR not connected (waiting for reconnect)",
                    file=sys.stderr,
                    flush=True,
                )
                return
            ok = mic.start_listening()
            if not ok:
                logger.error("Mic unavailable: %s", mic.last_error)
                return
            logger.info("Listening… (press ` to finish)")
        elif event.kind == PttEventKind.TURN_ENDED:
            logger.info("Turn ended — submitting to Grok…")
            audio = mic.stop_listening()
            machine.set_utterance(audio)
            if not client.is_connected:
                print(
                    "herdr-voice: ERROR not connected — turn discarded",
                    file=sys.stderr,
                    flush=True,
                )
                return
            asyncio.run_coroutine_threadsafe(client.commit_and_respond(), loop)

    def on_hotkey_fatal(reason: str) -> None:
        logger.error("Hotkey fatal: %s — shutting down", reason)
        loop.call_soon_threadsafe(shutdown.set)

    hotkey = BacktickHotkeyListener(machine, on_ptt, on_fatal=on_hotkey_fatal)

    await client.connect()
    hotkey.start()
    if not hotkey.healthy:
        raise SystemExit("Hotkeys failed to start")
    print(
        f"herdr-voice ready | model={config.model_id}\n"
        f"  ``  start speaking\n"
        f"  `   end turn & submit\n"
        f"  reconnect={'on' if config.reconnect_enabled else 'off'} "
        f"cli_timeout={config.cli_timeout_s}s\n"
        f"  Ctrl+C to quit",
        flush=True,
    )

    try:
        while not shutdown.is_set():
            await asyncio.sleep(0.5)
        print("herdr-voice: exiting after fatal hotkey failure", file=sys.stderr)
        raise SystemExit(2)
    finally:
        hotkey.stop()
        mic.close()
        speaker.close()
        await client.close()


if __name__ == "__main__":
    sys.exit(main())
