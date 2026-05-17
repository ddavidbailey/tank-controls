# Phase B: Voice Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an always-listening voice command pipeline that recognises spoken action names, fuzzy-matches them against the `[press]` config section, and emits real pynput keypresses.

**Architecture:** Four asyncio coroutines connected by bounded queues (`maxsize=5`): audio capture → VAD → STT (in `ThreadPoolExecutor`) → HID output. A `--dry-run` flag substitutes the HID coroutine with the existing dry-run logger for testing without macOS Accessibility permissions.

**Tech Stack:** `sounddevice`, `webrtcvad`, `faster-whisper`, `numpy`, `difflib` (stdlib), `pynput`, `asyncio`

---

## Before you begin

```bash
git checkout master && git pull origin master
git checkout -b phase-b/voice
```

---

### Task 1: VoiceConfig dataclass + `[voice]` section parsing

**Files:**
- Modify: `src/tank_controls/config/loader.py`
- Test: `tests/config/test_loader.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/config/test_loader.py` (keep all existing tests; add these below them):

```python
from tank_controls.config.loader import VoiceConfig


def test_voice_config_defaults_when_section_absent(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[profile]\nname = "test"\n')
    config = load_config(cfg)
    assert config.voice.vad_aggressiveness == 2
    assert config.voice.match_threshold == 0.8
    assert config.voice.action_cooldown_ms == 200


def test_voice_config_values_parsed(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text(
        '[profile]\nname = "test"\n'
        "[voice]\nvad_aggressiveness = 3\nmatch_threshold = 0.9\naction_cooldown_ms = 150\n"
    )
    config = load_config(cfg)
    assert config.voice.vad_aggressiveness == 3
    assert config.voice.match_threshold == 0.9
    assert config.voice.action_cooldown_ms == 150
```

- [ ] **Step 2: Run to verify they fail**

```
uv run pytest tests/config/test_loader.py::test_voice_config_defaults_when_section_absent tests/config/test_loader.py::test_voice_config_values_parsed -v
```

Expected: `ImportError` — `VoiceConfig` does not exist yet.

- [ ] **Step 3: Add VoiceConfig and update Config and load_config**

In `src/tank_controls/config/loader.py`, insert `VoiceConfig` before the `Config` class:

```python
@dataclass
class VoiceConfig:
    vad_aggressiveness: int = 2
    match_threshold: float = 0.8
    action_cooldown_ms: int = 200
```

Replace the `Config` dataclass with:

```python
@dataclass
class Config:
    profile_name: str
    press: dict[str, str] = field(default_factory=dict)
    hold: dict[str, str] = field(default_factory=dict)
    mouse: dict[str, str] = field(default_factory=dict)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
```

Replace the final `return` line in `load_config` with:

```python
    voice_raw: dict[str, Any] = data.get("voice", {})
    voice = VoiceConfig(
        vad_aggressiveness=int(voice_raw.get("vad_aggressiveness", 2)),
        match_threshold=float(voice_raw.get("match_threshold", 0.8)),
        action_cooldown_ms=int(voice_raw.get("action_cooldown_ms", 200)),
    )
    return Config(profile_name=profile_name, press=press, hold=hold, mouse=mouse, voice=voice)
```

- [ ] **Step 4: Run all loader tests to verify they pass**

```
uv run pytest tests/config/test_loader.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tank_controls/config/loader.py tests/config/test_loader.py
git commit -m "feat: add VoiceConfig dataclass and [voice] section parsing"
```

---

### Task 2: Intent matcher

**Files:**
- Create: `tests/audio/__init__.py`
- Create: `tests/audio/test_intent.py`
- Create: `src/tank_controls/audio/intent.py`

- [ ] **Step 1: Create the tests/audio package**

```bash
touch tests/audio/__init__.py
```

- [ ] **Step 2: Write failing tests**

Create `tests/audio/test_intent.py`:

```python
from tank_controls.audio.intent import match_intent


def test_exact_match_returns_action_and_binding():
    result = match_intent("fire", {"fire": "space"}, threshold=0.8)
    assert result == ("fire", "space")


def test_fuzzy_match_above_threshold():
    # "fired" vs "fire" — SequenceMatcher ratio ≈ 0.89
    result = match_intent("fired", {"fire": "space"}, threshold=0.8)
    assert result == ("fire", "space")


def test_below_threshold_returns_none():
    result = match_intent("hello", {"fire": "space"}, threshold=0.8)
    assert result is None


def test_empty_press_returns_none():
    result = match_intent("fire", {}, threshold=0.8)
    assert result is None


def test_underscore_converted_to_space():
    result = match_intent("shell one", {"shell_one": "1"}, threshold=0.8)
    assert result == ("shell_one", "1")


def test_best_match_selected_among_multiple():
    press = {"fire": "space", "range_finder": "ctrl+r"}
    result = match_intent("fire", press, threshold=0.8)
    assert result == ("fire", "space")


def test_multi_word_fuzzy_match():
    # "shell won" vs "shell one" — SequenceMatcher ratio ≈ 0.89
    result = match_intent("shell won", {"shell_one": "1"}, threshold=0.8)
    assert result == ("shell_one", "1")
```

- [ ] **Step 3: Run to verify they fail**

```
uv run pytest tests/audio/test_intent.py -v
```

Expected: `ModuleNotFoundError` — `tank_controls.audio.intent` does not exist yet.

- [ ] **Step 4: Implement match_intent**

Create `src/tank_controls/audio/intent.py`:

```python
import difflib


def match_intent(
    transcription: str,
    press: dict[str, str],
    threshold: float,
) -> tuple[str, str] | None:
    best_ratio = 0.0
    best_action: str | None = None
    best_binding: str | None = None

    for action, binding in press.items():
        candidate = action.replace("_", " ")
        ratio = difflib.SequenceMatcher(None, transcription, candidate).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_action = action
            best_binding = binding

    if best_ratio >= threshold and best_action is not None and best_binding is not None:
        return (best_action, best_binding)
    return None
```

- [ ] **Step 5: Run tests to verify they pass**

```
uv run pytest tests/audio/test_intent.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tank_controls/audio/intent.py tests/audio/__init__.py tests/audio/test_intent.py
git commit -m "feat: add fuzzy intent matcher for voice commands"
```

---

### Task 3: VAD state machine

**Files:**
- Create: `tests/audio/test_vad.py`
- Create: `src/tank_controls/audio/vad.py`

- [ ] **Step 1: Write failing tests**

Create `tests/audio/test_vad.py`:

```python
from unittest.mock import patch

from tank_controls.audio.vad import VoiceActivityDetector

# 320 samples × 2 bytes (int16) = 640 bytes per 20ms frame at 16kHz
FRAME = b"\x00" * 640


def make_detector(speech_sequence: list[bool]) -> VoiceActivityDetector:
    """Build a VoiceActivityDetector whose webrtcvad.Vad is mocked.

    speech_sequence controls what is_speech() returns on each call.
    """
    with patch("tank_controls.audio.vad.webrtcvad.Vad") as MockVad:
        MockVad.return_value.is_speech.side_effect = speech_sequence
        detector = VoiceActivityDetector(aggressiveness=2)
    return detector


def test_silence_frames_produce_no_output():
    detector = make_detector([False] * 10)
    results = [detector.process_frame(FRAME) for _ in range(10)]
    assert all(r is None for r in results)


def test_speech_frames_accumulate_without_output():
    detector = make_detector([True] * 5)
    results = [detector.process_frame(FRAME) for _ in range(5)]
    assert all(r is None for r in results)


def test_utterance_returned_after_trailing_silence():
    # 5 speech + 8 silence → utterance emitted on the 13th frame
    detector = make_detector([True] * 5 + [False] * 8)
    results = [detector.process_frame(FRAME) for _ in range(13)]
    assert results[-1] is not None
    assert len(results[-1]) == 13  # 5 speech + 8 silence frames in buffer


def test_partial_silence_does_not_emit():
    # 5 speech + 7 silence → threshold not reached yet
    detector = make_detector([True] * 5 + [False] * 7)
    results = [detector.process_frame(FRAME) for _ in range(12)]
    assert all(r is None for r in results)


def test_resets_after_utterance_second_utterance_detected():
    # Two utterances: 3 speech + 8 silence, then 3 speech + 8 silence
    sequence = [True] * 3 + [False] * 8 + [True] * 3 + [False] * 8
    detector = make_detector(sequence)
    results = [detector.process_frame(FRAME) for _ in range(len(sequence))]
    non_none = [r for r in results if r is not None]
    assert len(non_none) == 2
```

- [ ] **Step 2: Run to verify they fail**

```
uv run pytest tests/audio/test_vad.py -v
```

Expected: `ModuleNotFoundError` — `tank_controls.audio.vad` does not exist yet.

- [ ] **Step 3: Implement VoiceActivityDetector**

Create `src/tank_controls/audio/vad.py`:

```python
import logging
import webrtcvad

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16000
_SILENCE_THRESHOLD = 8  # consecutive silent frames before utterance is finalised (160 ms)


class VoiceActivityDetector:
    def __init__(self, aggressiveness: int) -> None:
        self._vad = webrtcvad.Vad(aggressiveness)
        self._buffer: list[bytes] = []
        self._silence_count = 0
        self._in_speech = False

    def process_frame(self, frame: bytes) -> list[bytes] | None:
        try:
            is_speech = self._vad.is_speech(frame, _SAMPLE_RATE)
        except Exception:
            logger.warning("webrtcvad rejected frame (wrong size?), discarding")
            return None

        if is_speech:
            self._in_speech = True
            self._silence_count = 0
            self._buffer.append(frame)
            return None

        if not self._in_speech:
            return None

        self._buffer.append(frame)
        self._silence_count += 1

        if self._silence_count >= _SILENCE_THRESHOLD:
            utterance = list(self._buffer)
            self._buffer = []
            self._silence_count = 0
            self._in_speech = False
            return utterance

        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/audio/test_vad.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tank_controls/audio/vad.py tests/audio/test_vad.py
git commit -m "feat: add VAD state machine for speech segment detection"
```

---

### Task 4: HID output with cooldown

**Files:**
- Create: `tests/hid/test_output.py`
- Create: `src/tank_controls/hid/output.py`

- [ ] **Step 1: Write failing tests**

Create `tests/hid/test_output.py`:

```python
from unittest.mock import call, patch

from pynput.keyboard import Key

from tank_controls.hid.output import KeyPresser


def test_single_key_press_calls_controller():
    with patch("tank_controls.hid.output.Controller") as MockController:
        controller = MockController.return_value
        presser = KeyPresser(cooldown_ms=0)
        result = presser.press("fire", "space")
        assert result is True
        controller.press.assert_any_call(Key.space)
        controller.release.assert_any_call(Key.space)


def test_combo_presses_modifier_before_key_releases_in_reverse():
    with patch("tank_controls.hid.output.Controller") as MockController:
        controller = MockController.return_value
        presser = KeyPresser(cooldown_ms=0)
        presser.press("range_finder", "ctrl+r")
        assert controller.press.call_args_list == [call(Key.ctrl), call("r")]
        assert controller.release.call_args_list == [call("r"), call(Key.ctrl)]


def test_cooldown_blocks_immediate_repeat():
    with patch("tank_controls.hid.output.Controller"), \
         patch("tank_controls.hid.output.time") as mock_time:
        mock_time.monotonic.side_effect = [0.0, 0.1]
        presser = KeyPresser(cooldown_ms=200)
        presser.press("fire", "space")   # first press at t=0.0
        result = presser.press("fire", "space")  # second at t=0.1 → 100ms < 200ms
        assert result is False


def test_cooldown_allows_press_after_elapsed():
    with patch("tank_controls.hid.output.Controller"), \
         patch("tank_controls.hid.output.time") as mock_time:
        mock_time.monotonic.side_effect = [0.0, 0.3]
        presser = KeyPresser(cooldown_ms=200)
        presser.press("fire", "space")   # first press at t=0.0
        result = presser.press("fire", "space")  # second at t=0.3 → 300ms > 200ms
        assert result is True


def test_cooldown_is_independent_per_action():
    with patch("tank_controls.hid.output.Controller"), \
         patch("tank_controls.hid.output.time") as mock_time:
        mock_time.monotonic.side_effect = [0.0, 0.05]
        presser = KeyPresser(cooldown_ms=200)
        presser.press("fire", "space")
        result = presser.press("range_finder", "ctrl+r")  # different action, no cooldown
        assert result is True
```

- [ ] **Step 2: Run to verify they fail**

```
uv run pytest tests/hid/test_output.py -v
```

Expected: `ModuleNotFoundError` — `tank_controls.hid.output` does not exist yet.

- [ ] **Step 3: Implement KeyPresser**

Create `src/tank_controls/hid/output.py`:

```python
import logging
import time

from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)

_MODIFIER_MAP: dict[str, Key] = {
    "ctrl": Key.ctrl,
    "alt": Key.alt,
    "shift": Key.shift,
}

_SPECIAL_KEY_MAP: dict[str, Key] = {
    "space": Key.space,
    "enter": Key.enter,
    "tab": Key.tab,
    "escape": Key.esc,
    **{f"f{i}": getattr(Key, f"f{i}") for i in range(1, 13)},
}


class KeyPresser:
    def __init__(self, cooldown_ms: int = 200) -> None:
        self._controller = Controller()
        self._cooldown_ms = cooldown_ms
        self._last_fired: dict[str, float] = {}

    def press(self, action_name: str, binding: str) -> bool:
        now = time.monotonic()
        if action_name in self._last_fired:
            if (now - self._last_fired[action_name]) * 1000 < self._cooldown_ms:
                return False
        self._last_fired[action_name] = now

        modifiers, key = self._parse_binding(binding)
        try:
            for mod in modifiers:
                self._controller.press(mod)
            self._controller.press(key)
            self._controller.release(key)
            for mod in reversed(modifiers):
                self._controller.release(mod)
        except Exception:
            logger.warning(
                "Failed to press '%s'. "
                "Grant Accessibility access in System Settings → Privacy & Security.",
                binding,
            )
            return False
        return True

    def _parse_binding(self, binding: str) -> tuple[list[Key], Key | str]:
        parts = binding.split("+")
        modifiers = [_MODIFIER_MAP[p] for p in parts[:-1] if p in _MODIFIER_MAP]
        key_str = parts[-1]
        key: Key | str = _SPECIAL_KEY_MAP.get(key_str, key_str)
        return modifiers, key
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/hid/test_output.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tank_controls/hid/output.py tests/hid/test_output.py
git commit -m "feat: add pynput KeyPresser with combo support and per-action cooldown"
```

---

### Task 5: Audio capture

**Files:**
- Create: `src/tank_controls/audio/capture.py`

No unit tests — hardware-dependent. Verified in the smoke test (Task 7).

- [ ] **Step 1: Implement AudioCapture**

Create `src/tank_controls/audio/capture.py`:

```python
import asyncio

import sounddevice as sd

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 20
FRAME_SIZE = SAMPLE_RATE * FRAME_DURATION_MS // 1000  # 320 samples per callback


class AudioCapture:
    def __init__(self, queue: asyncio.Queue[bytes], loop: asyncio.AbstractEventLoop) -> None:
        self._queue = queue
        self._loop = loop

    def _put_frame(self, data: bytes) -> None:
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            pass  # drop stale frame rather than block the event loop

    def _callback(
        self,
        indata: bytes,
        frames: int,
        time_info: object,
        status: object,
    ) -> None:
        self._loop.call_soon_threadsafe(self._put_frame, bytes(indata))

    def start(self) -> sd.RawInputStream:
        stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=FRAME_SIZE,
            dtype="int16",
            channels=1,
            callback=self._callback,
        )
        stream.start()
        return stream
```

- [ ] **Step 2: Verify the import is clean**

```
uv run python -c "from tank_controls.audio.capture import AudioCapture; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/tank_controls/audio/capture.py
git commit -m "feat: add sounddevice AudioCapture"
```

---

### Task 6: STT wrapper

**Files:**
- Create: `src/tank_controls/audio/stt.py`

No unit tests — model inference required. Verified in the smoke test (Task 7).

- [ ] **Step 1: Implement SpeechToText**

Create `src/tank_controls/audio/stt.py`:

```python
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from faster_whisper import WhisperModel


def _transcribe_sync(model: WhisperModel, audio: np.ndarray) -> str:
    segments, _ = model.transcribe(audio)
    return " ".join(seg.text for seg in segments)


class SpeechToText:
    def __init__(self, model: WhisperModel, executor: ThreadPoolExecutor) -> None:
        self._model = model
        self._executor = executor

    async def transcribe(self, frames: list[bytes]) -> str:
        audio = (
            np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0
        )
        loop = asyncio.get_running_loop()
        text: str = await loop.run_in_executor(
            self._executor, _transcribe_sync, self._model, audio
        )
        return re.sub(r"[^\w\s]", "", text).lower().strip()
```

- [ ] **Step 2: Verify the import is clean**

```
uv run python -c "from tank_controls.audio.stt import SpeechToText; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/tank_controls/audio/stt.py
git commit -m "feat: add faster-whisper SpeechToText wrapper"
```

---

### Task 7: Async pipeline wiring

**Files:**
- Modify: `src/tank_controls/main.py`

- [ ] **Step 1: Replace main.py with the full async pipeline**

Full replacement of `src/tank_controls/main.py`:

```python
import argparse
import asyncio
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import sounddevice as sd
from faster_whisper import WhisperModel

from tank_controls.audio.capture import AudioCapture
from tank_controls.audio.intent import match_intent
from tank_controls.audio.stt import SpeechToText
from tank_controls.audio.vad import VoiceActivityDetector
from tank_controls.config.errors import ConfigError
from tank_controls.config.loader import Config, load_config
from tank_controls.hid.dry_run import log_action
from tank_controls.hid.output import KeyPresser

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


async def _run_pipeline(config: Config, dry_run: bool) -> None:
    raw_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=_QUEUE_DEPTH)
    speech_queue: asyncio.Queue[list[bytes]] = asyncio.Queue(maxsize=_QUEUE_DEPTH)
    intent_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=_QUEUE_DEPTH)

    vad = VoiceActivityDetector(config.voice.vad_aggressiveness)
    loop = asyncio.get_running_loop()
    capture = AudioCapture(raw_queue, loop)

    with ThreadPoolExecutor(max_workers=1) as executor:
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        stt = SpeechToText(model, executor)
        try:
            stream = capture.start()
        except sd.PortAudioError as e:
            logging.error("Could not open microphone: %s", e)
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
            )
        finally:
            stream.stop()
            stream.close()


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
        help="Log recognised actions instead of sending keypresses",
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
```

- [ ] **Step 2: Run full test suite**

```
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 3: Run ruff and mypy**

```
uv run ruff check . && uv run ruff format --check . && uv run mypy src/
```

Expected: no errors.

- [ ] **Step 4: Smoke test with --dry-run**

Create a minimal config:

```bash
cat > /tmp/voice_test.toml << 'EOF'
[profile]
name = "voice-test"

[press]
fire = "space"
shell_one = "1"
shell_two = "2"
range_finder = "ctrl+r"
EOF
```

Run the pipeline:

```
uv run tank-controls --config /tmp/voice_test.toml --dry-run
```

Expected: program logs `Loaded profile: voice-test` and `Listening for: fire, shell one, shell two, range finder`. Speak "fire" — `INFO [DRY-RUN] press: space (fire)` should appear in the terminal. Press Ctrl+C to stop.

- [ ] **Step 5: Commit**

```bash
git add src/tank_controls/main.py
git commit -m "feat: wire asyncio voice pipeline with --dry-run flag"
```

- [ ] **Step 6: Push branch**

```bash
git push -u origin phase-b/voice
```
