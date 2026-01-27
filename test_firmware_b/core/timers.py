"""Non-blocking timer system for ESP32-B.

Imported by: core.actuator_loop, all actuator modules
Imports: time (ticks_ms, ticks_diff)

Provides elapsed() for non-blocking interval timing.
Usage:
    if elapsed("led_update", 100):
        # Runs every 100ms
        update_leds()

User override system:
- set_user_lock(name): Prevent elapsed() from returning True (persistent lock)
- clear_user_lock(name): Resume normal timing
- user_override_active(name): Check if lock is active

Useful for manual control scenarios where automatic updates should pause.
Example: User manually controls servo → lock "servo_auto" until timeout.
"""
from time import ticks_ms, ticks_diff  # type: ignore

_timers = {}

# Track user locks per timer/resource name. A lock stays active until cleared.
_user_actions = {}


def set_user_lock(name):
    """Set a persistent user lock for the given timer/resource name."""
    _user_actions[name] = True


def clear_user_lock(name):
    """Clear a previously set user lock (no-op if missing)."""
    _user_actions.pop(name, None)


def mark_user_action(name):
    """Backward-compatible alias to set a persistent user lock."""
    set_user_lock(name)


def user_override_active(name, window_ms=None):  # window_ms kept for signature compatibility
    """Return True if a user lock is active for this name."""
    return _user_actions.get(name, False)


def elapsed(name, interval, block_when_user_locked=False):
    """Return True if at least 'interval' ms elapsed since last True for name.

    If block_when_user_locked is True and a user lock has been set via
    set_user_lock()/mark_user_action(), this will return False until the lock
    is explicitly cleared (persistent override).
    """
    if block_when_user_locked and user_override_active(name):
        return False

    now = ticks_ms()
    last = _timers.get(name, 0)
    if ticks_diff(now, last) >= interval:
        _timers[name] = now
        return True
    return False
