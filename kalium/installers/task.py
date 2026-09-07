"""Background install task context."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class TaskContext:
    status_callback: Callable[[str], None]
    log_callback: Callable[[str], None]
    progress_callback: Callable[[float], None]
    cancel_flag: Callable[[], bool]

    def set_status(self, msg: str) -> None:
        self.status_callback(msg)

    def log(self, msg: str) -> None:
        self.log_callback(msg)

    def set_progress(self, p: float) -> None:
        self.progress_callback(p)

    def is_cancelled(self) -> bool:
        return self.cancel_flag()

    def run_cancellable(self, cmd: list[str], env: dict | None = None) -> int:
        proc = subprocess.Popen(cmd, env=env)
        while True:
            ret = proc.poll()
            if ret is not None:
                return ret
            if self.is_cancelled():
                proc.kill()
                proc.wait()
                raise RuntimeError("Cancelled")
            time.sleep(0.25)
