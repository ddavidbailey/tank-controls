from unittest.mock import MagicMock

from tank_controls.hid.panic import PanicGate


def _make_gate() -> tuple[PanicGate, MagicMock, MagicMock]:
    release_fn = MagicMock()
    on_toggle = MagicMock()
    return PanicGate(release_fn=release_fn, on_toggle=on_toggle), release_fn, on_toggle


def test_initially_not_paused() -> None:
    gate, _, _ = _make_gate()
    assert gate.is_paused() is False


def test_toggle_pauses() -> None:
    gate, _, _ = _make_gate()
    gate._on_hotkey()
    assert gate.is_paused() is True


def test_toggle_twice_resumes() -> None:
    gate, _, _ = _make_gate()
    gate._on_hotkey()
    gate._on_hotkey()
    assert gate.is_paused() is False


def test_release_fn_called_on_pause() -> None:
    gate, release_fn, _ = _make_gate()
    gate._on_hotkey()
    release_fn.assert_called_once()


def test_release_fn_not_called_on_resume() -> None:
    gate, release_fn, _ = _make_gate()
    gate._on_hotkey()
    release_fn.reset_mock()
    gate._on_hotkey()
    release_fn.assert_not_called()


def test_on_toggle_called_with_true_on_pause() -> None:
    gate, _, on_toggle = _make_gate()
    gate._on_hotkey()
    on_toggle.assert_called_once_with(True)


def test_on_toggle_called_with_false_on_resume() -> None:
    gate, _, on_toggle = _make_gate()
    gate._on_hotkey()
    on_toggle.reset_mock()
    gate._on_hotkey()
    on_toggle.assert_called_once_with(False)
