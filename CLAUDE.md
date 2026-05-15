# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A **local-only** Python assistant that maps voice commands and two-hand camera gestures to War Thunder game controls. No cloud STT or vision APIs. macOS is the primary target; Windows is a future release.

## Language and runtime

**Python 3.11+**. Use `uv`, Poetry, or a plain virtualenv — not Docker for the runtime loop (camera/mic/HID passthrough is incompatible with containers).

## Architecture

The pipeline is single-process by default:

```
Mic → AudioCapture → VAD → LocalSTT → IntentMap ──┐
                                                   ├─→ ActionMerger+Safety → HID → WarThunder
Cam → FrameCapture → TwoHandLandmarks → GestureAxes ┘
```

- **LocalSTT**: Vosk (default lean profile) or faster-whisper tiny/base int8 (rich profile)
- **Two-hand landmarks**: MediaPipe Hand Landmarker with `max_hands=2` — OpenCV handles capture and preprocessing only, not hand tracking
- **HID output**: `pynput` (baseline, cross-platform); `pyvjoy` + vJoy optional on Windows for analog axes
- **Concurrency**: `asyncio` with bounded queues and/or threads; keep capture, inference, and HID emission decoupled with backpressure

## Key technical constraints

- **RAM discipline**: War Thunder is the primary workload. Default to the `lean` profile (Vosk, 640×480 @ 15–30 FPS, CPU inference) to preserve VRAM for the game.
- **Two hands always**: both hands tracked concurrently. Don't reduce to one-hand unless adding an explicit optional fallback mode.
- **No cloud**: all STT and vision inference runs on-device.
- **macOS permissions**: `pynput` requires Accessibility (and likely Input Monitoring) granted in System Settings — prompt and document this clearly.

## Profiles

| Profile | Speech | Vision | Inference |
|---------|--------|--------|-----------|
| `lean` (default) | Vosk + fixed phrases | 640×480, 15–30 FPS | CPU (preserve VRAM) |
| `rich` | faster-whisper tiny/base int8 | Higher res/FPS | Optional GPU for STT |

## Phased roadmap

- **Phase A**: Config reader + dry-run logger (no actual input sent)
- **Phase B**: Voice — Vosk phrase list, push-to-talk optional
- **Phase C**: Vision — MediaPipe two-hand tracking, per-hand gesture → drive/turret axes
- **Phase D**: Fusion — merge modalities, debounce, global panic-disable hotkey, on-screen/audio state feedback

## Latency targets

| Path | Target |
|------|--------|
| Voice command | ~300–800 ms end-to-end |
| Gesture → control | ~50–150 ms perceived |
| Safety disable | Immediate (OS-global hotkey) |

## Open design questions (answer in README.md as decided)

- System RAM and GPU model (affects default profile)
- Camera placement and lighting
- Per-hand role assignment (e.g. left = drive, right = turret) and behavior when a hand leaves frame
- Turret control style: relative nudges vs absolute screen mapping
- Push-to-talk key vs always-listening vs wake phrase
- Online vs test-range only; ToS stance
