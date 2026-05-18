import argparse
import asyncio
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import sounddevice as sd  # type: ignore[import-untyped]

from tank_controls.audio.capture import AudioCapture
from tank_controls.audio.intent import match_intent
from tank_controls.audio.stt import SpeechToText
from tank_controls.audio.vad import VoiceActivityDetector
from tank_controls.config.errors import ConfigError
from tank_controls.config.loader import Config, VisionConfig, load_config
from tank_controls.hid.dry_run import log_action
from tank_controls.hid.output import KeyPresser
from tank_controls.vision.capture import FrameCapture
from tank_controls.vision.gesture import GestureState, compute_gesture
from tank_controls.vision.hid import GestureHID
from tank_controls.vision.landmarks import HandLandmarker

_QUEUE_DEPTH = 5


async def _vad_stage(
    raw_queue: asyncio.Queue[bytes],
    speech_queue: asyncio.Queue[list[bytes]],
    vad: VoiceActivityDetector,
) -> None:
    while True:
        frame = await raw_queue.get()
        utterance = vad.process_frame(frame)
        if utterance is not None:
            try:
                speech_queue.put_nowait(utterance)
            except asyncio.QueueFull:
                logging.warning("speech_queue full — utterance dropped")


async def _stt_stage(
    speech_queue: asyncio.Queue[list[bytes]],
    intent_queue: asyncio.Queue[tuple[str, str]],
    stt: SpeechToText,
    press: dict[str, str],
    threshold: float,
) -> None:
    while True:
        frames = await speech_queue.get()
        text = await stt.transcribe(frames)
        if not text:
            continue
        logging.debug("Transcribed: %r", text)
        result = match_intent(text, press, threshold)
        if result is not None:
            try:
                intent_queue.put_nowait(result)
            except asyncio.QueueFull:
                logging.warning("intent_queue full — intent dropped")


async def _hid_stage(
    intent_queue: asyncio.Queue[tuple[str, str]],
    presser: KeyPresser,
) -> None:
    while True:
        action_name, binding = await intent_queue.get()
        presser.press(action_name, binding)


async def _dry_run_stage(intent_queue: asyncio.Queue[tuple[str, str]]) -> None:
    while True:
        action_name, binding = await intent_queue.get()
        log_action(action_name, "press", binding)


async def _vision_stage(
    frame_queue: asyncio.Queue[Any],
    gesture_queue: asyncio.Queue[GestureState],
    landmarker: HandLandmarker,
    vision_config: VisionConfig,
) -> None:
    while True:
        frame = await frame_queue.get()
        hand_state = await landmarker.detect(frame)
        state = compute_gesture(hand_state, vision_config)
        try:
            gesture_queue.put_nowait(state)
        except asyncio.QueueFull:
            pass


async def _gesture_hid_stage(
    gesture_queue: asyncio.Queue[GestureState],
    hid: GestureHID,
) -> None:
    while True:
        state = await gesture_queue.get()
        hid.apply(state)


async def _run_pipeline(config: Config, dry_run: bool) -> None:
    # Voice queues
    raw_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=_QUEUE_DEPTH)
    speech_queue: asyncio.Queue[list[bytes]] = asyncio.Queue(maxsize=_QUEUE_DEPTH)
    intent_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=_QUEUE_DEPTH)
    # Vision queues
    frame_queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=2)
    gesture_queue: asyncio.Queue[GestureState] = asyncio.Queue(maxsize=_QUEUE_DEPTH)

    vad = VoiceActivityDetector(config.voice.energy_threshold)
    loop = asyncio.get_running_loop()
    audio_capture = AudioCapture(raw_queue, loop)
    initial_prompt = ", ".join(k.replace("_", " ") for k in config.press)

    cam_capture = FrameCapture(frame_queue, loop, config.vision)
    gesture_hid = GestureHID(config.hold)

    try:
        cam_capture.start()
    except RuntimeError as e:
        logging.error("Could not open camera: %s", e)
        sys.exit(1)

    with ThreadPoolExecutor(max_workers=2) as executor:
        stt = SpeechToText(str(config.voice.model), executor, initial_prompt=initial_prompt)
        landmarker = HandLandmarker(executor)
        try:
            stream = audio_capture.start()
        except sd.PortAudioError as e:
            logging.error("Could not open microphone: %s", e)
            cam_capture.stop()
            sys.exit(1)
        try:
            hid_coro = (
                _dry_run_stage(intent_queue)
                if dry_run
                else _hid_stage(intent_queue, KeyPresser(config.voice.action_cooldown_ms))
            )
            await asyncio.gather(
                _vad_stage(raw_queue, speech_queue, vad),
                _stt_stage(
                    speech_queue, intent_queue, stt, config.press, config.voice.match_threshold
                ),
                hid_coro,
                _vision_stage(frame_queue, gesture_queue, landmarker, config.vision),
                _gesture_hid_stage(gesture_queue, gesture_hid),
            )
        finally:
            stream.stop()
            stream.close()
            cam_capture.stop()
            landmarker.close()
            gesture_hid.release_all()


def main() -> None:
    parser = argparse.ArgumentParser(description="War Thunder multimodal controls")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="Path to keybind config file (default: config.toml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log recognised voice actions instead of sending keypresses",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        config = load_config(args.config)
    except ConfigError as e:
        logging.error(str(e))
        sys.exit(1)

    logging.info("Loaded profile: %s", config.profile_name)
    logging.info(
        "Listening for: %s",
        ", ".join(k.replace("_", " ") for k in config.press),
    )

    try:
        asyncio.run(_run_pipeline(config, args.dry_run))
    except KeyboardInterrupt:
        logging.info("Stopped.")
    except Exception as e:
        logging.error("Fatal error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
