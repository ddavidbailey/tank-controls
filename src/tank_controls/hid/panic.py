import threading
from collections.abc import Callable

from pynput.keyboard import GlobalHotKeys  # type: ignore[import-untyped]


class PanicGate:
    def __init__(
        self,
        release_fn: Callable[[], None],
        on_toggle: Callable[[bool], None],
    ) -> None:
        self._paused = threading.Event()
        self._release_fn = release_fn
        self._on_toggle = on_toggle
        self._listener: GlobalHotKeys | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._listener is not None:
            return
        self._listener = GlobalHotKeys({"<shift>+`": self._on_hotkey})
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener.join(timeout=1.0)
            self._listener = None

    def is_paused(self) -> bool:
        return self._paused.is_set()

    def _on_hotkey(self) -> None:
        with self._lock:
            if self._paused.is_set():
                self._paused.clear()
                toggled_to = False
            else:
                self._paused.set()
                toggled_to = True
        if toggled_to:
            self._release_fn()
        self._on_toggle(toggled_to)
