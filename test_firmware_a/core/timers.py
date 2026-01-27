"""Non-blocking timer management module with user override support.

Imported by: core.sensor_loop, core.actuator_loop (B), communication.*, actuators.*, sensors.*
Imports: time (MicroPython built-in)

Provides interval-based timing without blocking execution.
Supports persistent user locks to prevent automated updates when user manually controls a resource.

Key features:
- elapsed(): Returns True when interval has passed, False otherwise
- User locks: Block automated updates until explicitly cleared
- Millisecond precision using ticks_ms() for overflow safety
- No blocking delays - purely interval-based logic

Usage example:
    if elapsed("sensor_read", 1000):  # Every 1 second
        read_sensor()
    
    # With user lock:
    if elapsed("led_update", 100, block_when_user_locked=True):
        update_led()  # Won't run if user manually set LED
"""

from time import ticks_ms, ticks_diff  # type: ignore

# Timer state: stores last trigger timestamp for each named timer
_timers = {}

# User lock tracking: prevents automated updates when user takes manual control
# A lock stays active until explicitly cleared via clear_user_lock()
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
