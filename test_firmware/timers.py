import time

_timers = {}

def elapsed(name, interval):
    now = time.ticks_ms()
    last = _timers.get(name, 0)
    if time.ticks_diff(now, last) >= interval:
        _timers[name] = now
        return True
    return False
