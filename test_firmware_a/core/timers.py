from time import ticks_ms, ticks_diff  # type: ignore

_timers = {}

def elapsed(name, interval):
    now = ticks_ms()
    last = _timers.get(name, 0)
    if ticks_diff(now, last) >= interval:
        _timers[name] = now
        return True
    return False
