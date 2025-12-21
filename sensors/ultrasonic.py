from machine import Pin, time_pulse_us, Timer  # type: ignore
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

# Non-blocking variables
_echo_start_time = 0
_echo_duration = 0
_measurement_pending = False
_measurement_ready = False


def init_ultrasonic():
    global _trig, _echo
    _trig = Pin(ULTRASONIC_TRIG_PIN, Pin.OUT)
    _echo = Pin(ULTRASONIC_ECHO_PIN, Pin.IN)
    _trig.value(0)
    # Set up interrupt for echo pin
    _echo.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_echo_interrupt)
    log("ultrasonic", "Ultrasonic sensor initialized (non-blocking)")


def _echo_interrupt(pin):
    global _echo_start_time, _echo_duration, _measurement_pending, _measurement_ready
    if not _measurement_pending:
        return
    now = time.ticks_us()
    if pin.value() == 1:  # Rising edge
        _echo_start_time = now
    else:  # Falling edge
        if _echo_start_time > 0:
            _echo_duration = time.ticks_diff(now, _echo_start_time)
            _measurement_ready = True
            _measurement_pending = False


def read_ultrasonic():
    global _last_read_ms, _measurement_pending, _measurement_ready, _echo_duration

    now = time.ticks_ms()
    if time.ticks_diff(now, _last_read_ms) < READ_INTERVAL_MS:
        return

    _last_read_ms = now

    if _measurement_pending:
        # Still waiting for previous measurement
        return

    if _measurement_ready:
        # Process completed measurement
        duration = _echo_duration
        _measurement_ready = False
        if duration > 0:
            distance_cm = duration * SPEED_OF_SOUND_CM_US
            state.sensor_data["ultrasonic_distance_cm"] = round(distance_cm, 2)
        else:
            log("ultrasonic", "Invalid duration")
            state.sensor_data["ultrasonic_distance_cm"] = None
        return

    # Start new measurement
    try:
        _measurement_pending = True
        _echo_start_time = 0
        _echo_duration = 0
        # Send trigger pulse (10us) using timer for precision
        _trig.value(1)
        time.sleep_us(10)
        _trig.value(0)
    except Exception as e:
        log("ultrasonic", f"Trigger error: {e}")
        _measurement_pending = False
        state.sensor_data["ultrasonic_distance_cm"] = None
