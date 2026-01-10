from time import ticks_ms, ticks_diff  # type: ignore

_timers = {}

# Track last user actions per timer name to apply override windows
_user_actions = {}

# Default override window after a user action (milliseconds)
USER_OVERRIDE_WINDOW_MS = 20000


def mark_user_action(name):
    """Record a user action for a given timer/resource name.

    Use the same 'name' that producer logic passes to elapsed() when you want
    to temporarily prevent that producer from running.
    """
    _user_actions[name] = ticks_ms()


def user_override_active(name, window_ms=USER_OVERRIDE_WINDOW_MS):
    """Return True if a recent user action should block this timer name.

    Automatically clears expired entries lazily when queried.
    """
    ts = _user_actions.get(name)
    if ts is None:
        return False
    now = ticks_ms()
    if ticks_diff(now, ts) < window_ms:
        return True
    # Expired, clean up
    try:
        del _user_actions[name]
    except KeyError:
        pass
    return False


def elapsed(name, interval, block_when_user_locked=False):
    """Return True if at least 'interval' ms elapsed since last True for name.

    If block_when_user_locked is True and a recent user action has been marked
    via mark_user_action(name), this will return False until the override
    window ends. This allows user commands to temporarily prevent automatic
    producers (e.g., remote logic) from running for that name.
    """
    if block_when_user_locked and user_override_active(name):
        return False

    now = ticks_ms()
    last = _timers.get(name, 0)
    if ticks_diff(now, last) >= interval:
        _timers[name] = now
        return True
    return False
