"""Ultrasonic distance sensor module (HC-SR04).

Measures distance using simple blocking reads with light smoothing.
"""
from machine import Pin, time_pulse_us  # type: ignore
from time import ticks_ms, ticks_diff, sleep_us  # type: ignore

from core import state
from debug.debug import log
from config.config import ULTRASONIC_TRIG_PIN, ULTRASONIC_ECHO_PIN

# Speed of sound (cm/us)
SPEED_OF_SOUND_CM_US = 0.0343 / 2

# Internal state
_trig = None
_echo = None
_last_read_ms = 0
READ_INTERVAL_MS = 100

_measurement_count = 0
_failed_measurements = 0
_distance_log_counter = 0
_last_good_distance_cm = None


def init_ultrasonic():
    global _trig, _echo
    try:
        _trig = Pin(ULTRASONIC_TRIG_PIN, Pin.OUT)
        _echo = Pin(ULTRASONIC_ECHO_PIN, Pin.IN)
        _trig.value(0)
        log("ultrasonic", "init_ultrasonic: Ultrasonic sensor initialized (blocking)")
        return True
    except Exception as e:
        log("ultrasonic", "init_ultrasonic: Initialization failed: {}".format(e))
        _trig = None
        _echo = None
        return False


def _smooth_distance(raw_distance):
    """Light smoothing: blend with last good value to reduce jitter."""
    global _last_good_distance_cm
    if _last_good_distance_cm is None:
        _last_good_distance_cm = raw_distance
    else:
        _last_good_distance_cm = (_last_good_distance_cm * 0.7) + (raw_distance * 0.3)
    return round(_last_good_distance_cm, 2)


def read_ultrasonic():
    global _last_read_ms, _measurement_count, _failed_measurements, _distance_log_counter
    
def read_ultrasonic():
    global _last_read_ms, _measurement_count, _failed_measurements, _distance_log_counter
    
    if _trig is None or _echo is None:
        return

    now = ticks_ms()
    if ticks_diff(now, _last_read_ms) < READ_INTERVAL_MS:
        return

    _last_read_ms = now
    
    try:
        # Simple blocking read
        _trig.value(0)
        sleep_us(2)
        _trig.value(1)
        sleep_us(15)
        _trig.value(0)
        
        duration = time_pulse_us(_echo, 1, 30000)  # 30ms timeout
        _measurement_count += 1
        
        if duration > 0:
            distance_cm = duration * SPEED_OF_SOUND_CM_US
            
            if 2 <= distance_cm <= 400:
                blended = _smooth_distance(distance_cm)
                state.sensor_data["ultrasonic_distance_cm"] = blended
                _distance_log_counter += 1
                if _distance_log_counter % 10 == 0:
                    log("ultrasonic", "ok dist {:.2f} cm dur {}us (count {}, failed {})".format(
                        blended, duration, _measurement_count, _failed_measurements))
            else:
                state.sensor_data["ultrasonic_distance_cm"] = _last_good_distance_cm
                _failed_measurements += 1
        else:
            # Timeout or no echo
            state.sensor_data["ultrasonic_distance_cm"] = _last_good_distance_cm
            _failed_measurements += 1
            
    except Exception as e:
        log("ultrasonic", "read error: {}".format(e))
        state.sensor_data["ultrasonic_distance_cm"] = _last_good_distance_cm
        _failed_measurements += 1

