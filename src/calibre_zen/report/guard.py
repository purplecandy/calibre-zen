#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, Nadeem Siddique

"""
Every module installs, or fails alone.

`hooks.py` installs the overlay's parts in a sequence, and until this existed
a raise in the third left the fourth through eighth uninstalled and the
palette change half-done. Now each call is guarded: a failure is printed,
that module is recorded as failed and skipped for the session, and the rest
carry on. Stock calibre with a Zen stylesheet is an acceptable Tuesday; a
window that does not open is not.

A failure here is also the most valuable report the project can receive. It
is the signal, arriving from the field the day upstream ships, that calibre
renamed something one of the wraps reaches for. So each one is kept as an
event and offered for sending once there is a window to ask from.
"""

import sys
import traceback
from collections.abc import Callable

OK = 'ok'
OFF = 'off'
FAILED = 'failed'

_states: dict[str, str] = {}
_pending: list[dict] = []
_offered = False


def run_install(name: str, fn: Callable[[], bool]) -> bool:
    """
    Call a module's `install()`. Returns whether it is active.

    A module that raises is marked FAILED and never retried in this process:
    `install()` functions are idempotent by contract and the palette hook calls
    the sequence again on every theme change.
    """
    if _states.get(name) == FAILED:
        return False
    try:
        active = bool(fn())
    except Exception as e:
        _states[name] = FAILED
        traceback.print_exc()
        print(f'calibre-zen: {name} did not install and is off for this session', file=sys.stderr)
        _record(name, e)
        return False
    _states[name] = OK if active else OFF
    return active


def _record(name: str, e: BaseException) -> None:
    try:
        from calibre_zen.report import event

        _pending.append(event.build(e, mechanism_type='zen.install', handled=True, tags={'zen.module': name}))
    except Exception:
        # The reporter itself may be what failed; the traceback above is
        # already on stderr, which is where we would have ended up anyway.
        traceback.print_exc()


def states() -> dict[str, str]:
    return dict(_states)


def failed() -> list[str]:
    return [k for k, v in _states.items() if v == FAILED]


def pending() -> list[dict]:
    return list(_pending)


def take_pending() -> list[dict]:
    "The queued failure events, once. A second call is empty."
    global _offered
    ans = list(_pending)
    _pending.clear()
    _offered = True
    return ans
