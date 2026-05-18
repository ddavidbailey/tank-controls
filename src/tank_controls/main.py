import argparse
import asyncio
import logging
import queue as _tq
import sys
import threading
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
from tank_controls.vision.debug import draw_debug_overlay
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


async def _dry_run_gesture_stage(gesture_queue: asyncio.Queue[GestureState]) -> None:
    while True:
        state = await gesture_queue.get()
        if state.hold_actions:
            logging.info("[DRY-RUN] gesture: hold %s", sorted(state.hold_actions))
        if state.mouse_delta != (0, 0):
            logging.info("[DRY-RUN] gesture: mouse_move %s", state.mouse_delta)


async def _vision_stage(
    frame_queue: asyncio.Queue[Any],
    gesture_queue: asyncio.Queue[GestureState],
    landmarker: HandLandmarker,
    vision_config: VisionConfig,
    display_queue: "_tq.Queue[Any] | None" = None,
) -> None:
    while True:
        frame = await frame_queue.get()
        hand_state = await landmarker.detect(frame)
        state = compute_gesture(hand_state, vision_config)
        try:
            gesture_queue.put_nowait(state)
        except asyncio.QueueFull:
            pass
        if display_queue is not None:
            import cv2

            overlay = draw_debug_overlay(frame, hand_state, state, vision_config)
            bgr = cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR)
            try:
                display_queue.put_nowait(bgr)
            except _tq.Full:
                pass


async def _gesture_hid_stage(
    gesture_queue: asyncio.Queue[GestureState],
    hid: GestureHID,
) -> None:
    while True:
        state = await gesture_queue.get()
        hid.apply(state)


async def _run_pipeline(
    config: Config,
    dry_run: bool,
    display_queue: "_tq.Queue[Any] | None" = None,
) -> None:
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
            gesture_hid_coro = (
                _dry_run_gesture_stage(gesture_queue)
                if dry_run
                else _gesture_hid_stage(gesture_queue, gesture_hid)
            )
            await asyncio.gather(
                _vad_stage(raw_queue, speech_queue, vad),
                _stt_stage(
                    speech_queue, intent_queue, stt, config.press, config.voice.match_threshold
                ),
                hid_coro,
                _vision_stage(frame_queue, gesture_queue, landmarker, config.vision, display_queue),
                gesture_hid_coro,
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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show camera feed with quadrant zone overlay",
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

    if args.debug:
        import cv2

        display_q: _tq.Queue[Any] = _tq.Queue(maxsize=2)
        exc_holder: list[BaseException] = []

        def _run_in_thread() -> None:
            try:
                asyncio.run(_run_pipeline(config, args.dry_run, display_q))
            except KeyboardInterrupt:
                pass
            except Exception as exc:
                exc_holder.append(exc)

        t = threading.Thread(target=_run_in_thread, daemon=True)
        t.start()

        cv2.namedWindow("Tank Controls — Vision Debug", cv2.WINDOW_AUTOSIZE)
        try:
            while t.is_alive():
                try:
                    bgr = display_q.get_nowait()
                    cv2.imshow("Tank Controls — Vision Debug", bgr)
                except _tq.Empty:
                    pass
                if cv2.waitKey(16) == 27:  # ESC quits
                    break
        except KeyboardInterrupt:
            logging.info("Stopped.")
        finally:
            cv2.destroyAllWindows()

        t.join(timeout=2.0)
        if exc_holder:
            logging.error("Fatal error: %s", exc_holder[0])
            sys.exit(1)
    else:
        try:
            asyncio.run(_run_pipeline(config, args.dry_run))
        except KeyboardInterrupt:
            logging.info("Stopped.")
        except Exception as e:
            logging.error("Fatal error: %s", e)
            sys.exit(1)


if __name__ == "__main__":
    main()
