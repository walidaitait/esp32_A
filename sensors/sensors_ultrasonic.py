from machine import Pin, time_pulse_us  # type: ignore
import time

import state
from debug import log
from config import ULTRASONIC_TRIG_PIN, ULTRASONIC_ECHO_PIN

# Speed of sound (cm/us)
SPEED_OF_SOUND_CM_US = 0.0343 / 2

# Internal state
_trig = None
_echo = None
_last_read_ms = 0
READ_INTERVAL_MS = 100   # adjust if needed


def init_ultrasonic():
    global _trig, _echo
    _trig = Pin(ULTRASONIC_TRIG_PIN, Pin.OUT)
    _echo = Pin(ULTRASONIC_ECHO_PIN, Pin.IN)
    _trig.value(0)
    log("ultrasonic", "Ultrasonic sensor initialized")


def read_ultrasonic():
    global _last_read_ms

    now = time.ticks_ms()
    if time.ticks_diff(now, _last_read_ms) < READ_INTERVAL_MS:
        return

    _last_read_ms = now

    try:
        # Send trigger pulse (10us)
        _trig.value(0)
        time.sleep_us(2)
        _trig.value(1)
        time.sleep_us(10)
        _trig.value(0)

        # Measure echo pulse
        duration = time_pulse_us(_echo, 1, 30000)  # timeout ~5m

        if duration < 0:
            log("ultrasonic", "Echo timeout")
            state.ultrasonic_distance_cm = None
            return

        distance_cm = duration * SPEED_OF_SOUND_CM_US
        state.ultrasonic_distance_cm = round(distance_cm, 2)

    except Exception as e:
        log("ultrasonic", f"Read error: {e}")
        state.ultrasonic_distance_cm = None
