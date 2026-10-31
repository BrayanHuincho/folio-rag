import logging
import threading
from collections.abc import Callable
from pathlib import Path

from watchfiles import watch

log = logging.getLogger(__name__)


class FolderWatcher:
    def __init__(self, path: Path, on_change: Callable[[set[str]], None], debounce_ms: int = 1500):
        self.path = path
        self._on_change = on_change
        self._debounce = debounce_ms
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"watch:{path.name}", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            for changes in watch(
                self.path,
                debounce=self._debounce,
                stop_event=self._stop,
                raise_interrupt=False,
                ignore_permission_denied=True,
            ):
                try:
                    self._on_change({path for _, path in changes})
                except Exception:
                    log.exception("watch callback failed for %s", self.path)
        except Exception:
            # la carpeta puede desaparecer (USB desconectado, etc.); no tumbamos la app
            log.warning("stopped watching %s", self.path, exc_info=True)
