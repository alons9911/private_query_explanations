"""Cooperative time limits for timed runs.

Long loops (the statistics build, lazy histograms, the B2 enumeration) call
:func:`check`; inside ``with deadline(seconds):`` it raises :class:`RunTimeout`
once the limit has passed.  Outside a deadline it is a no-op.
"""

from __future__ import annotations

import time
from contextlib import contextmanager

_deadline: float | None = None


class RunTimeout(TimeoutError):
    def __init__(self, msg: str = "time limit reached", info: dict | None = None):
        super().__init__(msg)
        self.info = info or {}


def check() -> None:
    if _deadline is not None and time.perf_counter() > _deadline:
        raise RunTimeout()


@contextmanager
def deadline(seconds: float | None):
    """Run the block with a time limit of ``seconds`` (None = no limit); limits do not nest."""
    global _deadline
    prev = _deadline
    _deadline = None if seconds is None else time.perf_counter() + float(seconds)
    try:
        yield
    finally:
        _deadline = prev
