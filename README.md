# War Thunder Tank Controller (Voice and Video Interaction)

## Project Goal:

If you ever felt like you're getting too good at driving a tank using mouse and keyboard? This new tank controlling method allows you to use a combination of arms/hands and voice to manipulate tank controls along with weapon selection and firing. You'll certianlly need some practice to get use to it, but if you're up for the challange give it a shot (pun intended)!

## Requirements:

- Stable on MacOS 26.5 (Tahoe). Haven't tested on any other versions.
- Enough RAM for game and program
- Python >= 3.11
- Working webcam and mic. Better results from good devices
- Lots of patience! You'll die in game a lot
- Be sure to provide camera and mic accessibility to the terminal when prompted or it will not work! Also key mapping should be the same in game as they are within this program.

## Usage:

Once in desired directory:

1. `uv sync`
2. `uv run tank-controls`: base execution

#### Flags:

`--dry-run`: if you want to verify inputs are working without manipulating device yet. Stictly for testing purposes.

`--overlay-feedback`: if you want to see different quadrants/movement areas

`--log-feedback`: if you want to see constant logging inside the terminal window

`--debug`: also available but WIP at the moment

## Controls:

### **PANIC BUTTON IS "="** and will stop all inputs

### <u>Voice Commands:</u>

`Fire`: Left Click (Mouse 1)

`Scope`: Shift (WIP)

`Range Finder`: Command

`1-4`: #1-4 (For shell selection)

### <u>Camera: </u>

Left arm/hand control the tank movement. Right arm/hand control turret movement. To get a better idea of where the camera is viewing and quadrant locations, use `--dry-run --overlay-feedback` flags.

### Technical Information

**Architecture.** Single local process: microphone audio is segmented by voice-activity detection, transcribed with [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) on Apple Silicon, and matched to action names in `config.toml` under `[press]`. The webcam feed is processed with MediaPipe Hand Landmarker (two hands); the left hand drives tank movement via held keys in `[hold]`, and the right hand sends relative mouse movement for the turret.

**Privacy.** No cloud speech or vision APIs; models and inference run on your machine.

**Stack.** Python 3.11+ · mlx-whisper · MediaPipe · OpenCV · sounddevice · pynput (keyboard/mouse). On macOS, relative mouse events use Quartz so War Thunder receives delta fields correctly.

**Safety.** Global hotkey `=` toggles pause; when paused, held keys are released and no new input is sent.

**Configuration.** See `config.toml`. Voice sensitivity: `[voice]` `energy_threshold`, `match_threshold`. Vision: `[vision]` resolution, `quadrant_threshold`, `max_mouse_speed`. Key bindings must match War Thunder’s in-game controls.

**Further docs.** Implementation phases and design notes live under `docs/superpowers/` (for contributors).
