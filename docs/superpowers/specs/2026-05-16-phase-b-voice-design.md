# Phase B: Voice Pipeline Design

**Date:** 2026-05-16
**Scope:** Always-listening voice command recognition — audio capture, VAD, STT, intent matching, real HID output

## Goal

Recognise spoken command names and emit real keypresses via pynput. Proves the full voice pipeline end-to-end before gestures (Phase C) or fusion (Phase D) are introduced.

---

## Config additions

A new `[voice]` section in the TOML controls pipeline tuning. All fields are optional with the defaults shown.

```toml
[voice]
vad_aggressiveness = 2      # webrtcvad aggressiveness 0–3 (default 2)
match_threshold = 0.8       # fuzzy match minimum ratio 0.0–1.0 (default 0.8)
action_cooldown_ms = 200    # minimum ms between repeated same-action fires (default 200)
```

Voice actions are **not** defined separately. The intent matcher reads the existing `[press]` section and derives spoken phrases from action names (`shell_one` → `"shell one"`). No changes to `[press]`, `[hold]`, or `[mouse]` are needed.

---

## Pipeline

Data flows through four stages connected by bounded `asyncio.Queue(maxsize=5)` instances. The bound prevents stale audio from accumulating if STT falls behind — excess items are dropped rather than queued indefinitely.

```
sounddevice callback
      │  raw 20ms PCM frames
      ▼
 [raw_queue]
      │
      ▼  VAD coroutine
 [speech_queue]   ← complete utterance (concatenated frames)
      │
      ▼  STT coroutine (mlx-whisper in ThreadPoolExecutor)
 [intent_queue]   ← matched (action_name, key_binding) pair
      │
      ▼  HID coroutine
   pynput keypress
```

---

## Audio capture (`audio/capture.py`)

- Opens a mono `sounddevice.RawInputStream` at **16 000 Hz, int16**
  - 16 kHz satisfies webrtcvad's required sample rates (8 000 / 16 000 / 32 000 Hz)
  - No resampling needed — mlx-whisper also expects 16 kHz
- Blocksize: **320 samples** (20 ms at 16 kHz) — the frame duration webrtcvad requires
- sounddevice fires its callback on a background thread; frames are forwarded to `raw_queue` via `loop.call_soon_threadsafe` so the asyncio event loop is never touched from the wrong thread
- Capture stage owns no logic — it is a pure data mover

---

## Voice activity detection (`audio/vad.py`)

- Uses `webrtcvad.Vad(aggressiveness)` where aggressiveness comes from config (default 2)
- Reads 20 ms frames from `raw_queue` and classifies each as speech or silence
- Implements a simple state machine:

| State | Transition |
|---|---|
| **Silence** | Speech frame detected → enter **Speech** |
| **Speech** | Accumulate frames into buffer |
| **Speech** | 8 consecutive silent frames (160 ms) → utterance complete → push buffer to `speech_queue`, reset to **Silence** |

- 160 ms trailing silence window prevents mid-phrase cuts without adding noticeable lag
- Discards all frames while in Silence state — nothing queued upstream

---

## Speech-to-text (`audio/stt.py`)

- Model loaded on first transcription call via `mlx_whisper.transcribe(path_or_hf_repo=...)` and cached by the mlx-whisper library. Default: `mlx-community/whisper-tiny.en-mlx`
- Receives a complete utterance (list of raw int16 frames) from `speech_queue`
- Concatenates frames into a single NumPy array and normalises to float32 in `[-1.0, 1.0]`
- Transcription runs in a `ThreadPoolExecutor` via `loop.run_in_executor` so the event loop stays live during inference
- Result is normalised: lowercased, punctuation stripped
- Passes normalised text to intent matching; if transcription returns empty string, utterance is discarded

---

## Intent matching (`audio/intent.py`)

- Receives normalised transcription text and the loaded `Config`
- Only considers `config.press` — hold and mouse actions are out of scope for voice
- Converts each action name to a candidate phrase: `shell_one` → `"shell one"`
- Scores transcription against every candidate using `difflib.SequenceMatcher(None, transcription, candidate).ratio()`
- Selects the highest-scoring match; if it meets `match_threshold` (default 0.8), pushes `(action_name, key_binding)` to `intent_queue`
- If no candidate clears the threshold, the utterance is silently discarded

**Example matches at threshold 0.8:**

| Spoken | Transcribed | Best match | Score | Result |
|---|---|---|---|---|
| "fire" | "fire" | fire | 1.00 | ✓ |
| "fire" | "fired" | fire | 0.89 | ✓ |
| "shell one" | "shell won" | shell_one | 0.89 | ✓ |
| "hello" | "hello" | — | ≤0.40 | discarded |

---

## HID output (`hid/output.py`)

- Uses `pynput.keyboard.Controller`
- Parses the binding string from config on the `+` separator: `ctrl+r` → modifiers `["ctrl"]`, key `"r"`
- Press sequence: press all modifiers → press key → release key → release modifiers (reverse order)
- Single keys (no `+`) skip modifier logic entirely
- **Per-action cooldown:** 200 ms (configurable via `action_cooldown_ms`). Tracks last-fired timestamp per action name. Repeat fires within the cooldown window are dropped. This prevents VAD mis-segmentation from double-firing a command. Intentional rapid repeats (e.g. two "fire" presses 400 ms apart) still work.
- macOS Accessibility permission failure: caught and logged with a message directing the user to System Settings → Privacy & Security → Accessibility. Process does not crash.

---

## Updated `main.py`

1. Parse `--config` and optional `--dry-run` flag via argparse
2. Load config via `loader.py` — exit on `ConfigError` as before
3. Instantiate `SpeechToText` with the model path from config (mlx-whisper loads and caches the model on first use)
4. Start the asyncio event loop with all four coroutines running concurrently via `asyncio.gather`
5. `--dry-run` flag substitutes the HID coroutine with the existing `log_action` dry-run logger — useful for verifying the full voice pipeline without macOS Accessibility permissions

---

## Error handling

| Failure | Behaviour |
|---|---|
| Mic not found / permission denied | Log error at startup, exit with code 1 |
| webrtcvad frame size mismatch | Caught per-frame, logged at WARNING, frame discarded |
| mlx-whisper model not cached / download fails | Propagates as exception at startup, logged, exit code 1 |
| Empty transcription | Silently discarded, pipeline continues |
| No intent match | Silently discarded, pipeline continues |
| pynput Accessibility denied | Logged with guidance, action dropped, pipeline continues |

---

## Testing

Hardware-dependent stages (capture, STT, HID against OS) are not unit-tested. Logic stages are:

| File | What is tested |
|---|---|
| `tests/audio/test_intent.py` | Exact matches, fuzzy matches, threshold rejection, underscore→space conversion, empty press section |
| `tests/audio/test_vad.py` | State machine transitions with synthetic speech/silence frame sequences; trailing silence window; buffer reset |
| `tests/hid/test_output.py` | Binding parser (single key, combo, invalid); cooldown logic (mocked time); pynput calls mocked |

---

## Files created or modified

| File | Action |
|---|---|
| `src/tank_controls/audio/capture.py` | Create |
| `src/tank_controls/audio/vad.py` | Create |
| `src/tank_controls/audio/stt.py` | Create |
| `src/tank_controls/audio/intent.py` | Create |
| `src/tank_controls/hid/output.py` | Create |
| `src/tank_controls/config/loader.py` | Modify — add `VoiceConfig` dataclass, parse `[voice]` section |
| `src/tank_controls/main.py` | Modify — asyncio pipeline, `--dry-run` flag |
| `tests/audio/__init__.py` | Create |
| `tests/audio/test_intent.py` | Create |
| `tests/audio/test_vad.py` | Create |
| `tests/hid/test_output.py` | Create |
