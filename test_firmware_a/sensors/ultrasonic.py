"""Ultrasonic distance sensor module (HC-SR04).

Measures distance using non-blocking interrupt-based echo detection.
"""
from machine import Pin, time_pulse_us, Timer  # type: ignore
from time import ticks_ms, ticks_us, ticks_diff, sleep_us  # type: ignore

from core import state
from debug.debug import log
from config.config import ULTRASONIC_TRIG_PIN, ULTRASONIC_ECHO_PIN

# Speed of sound (cm/us)
SPEED_OF_SOUND_CM_US = 0.0343 / 2

# Internal state
_trig = None
_echo = None
_last_read_ms = 0
READ_INTERVAL_MS = 100   # Adjust if needed

# Non-blocking variables
_echo_start_time = 0
_echo_duration = 0
_measurement_pending = False
_measurement_ready = False
_measurement_count = 0
_failed_measurements = 0
_consecutive_timeouts = 0
_trigger_time_ms = 0  # Tempo di inizio della misurazione
_timeout_log_counter = 0
_distance_log_counter = 0
_last_good_distance_cm = None


def init_ultrasonic():
    global _trig, _echo
    try:
        _trig = Pin(ULTRASONIC_TRIG_PIN, Pin.OUT)
        # Prefer a pull-down on ECHO to avoid floating input if available
        try:
            _echo = Pin(ULTRASONIC_ECHO_PIN, Pin.IN, Pin.PULL_DOWN)
        except Exception:
            _echo = Pin(ULTRASONIC_ECHO_PIN, Pin.IN)
        _trig.value(0)
        # Set up interrupt for echo pin
        _echo.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_echo_interrupt)
        log("ultrasonic", "init_ultrasonic: Ultrasonic sensor initialized (non-blocking)")
        return True
    except Exception as e:
        log("ultrasonic", "init_ultrasonic: Initialization failed: {}".format(e))
        _trig = None
        _echo = None
        return False


def _echo_interrupt(pin):
    global _echo_start_time, _echo_duration, _measurement_pending, _measurement_ready
    if not _measurement_pending:
        return
    now = ticks_us()
    if pin.value() == 1:  # Rising edge
        _echo_start_time = now
    else:  # Falling edge
        if _echo_start_time > 0:
            _echo_duration = ticks_diff(now, _echo_start_time)
            _measurement_ready = True
            _measurement_pending = False


def _blocking_single_read(timeout_us=30000):
    """One-shot blocking read used as fallback when interrupts miss echoes."""
    global _trig, _echo
    try:
        _trig.value(0)
        sleep_us(2)
        _trig.value(1)
        sleep_us(15)
        _trig.value(0)

        duration = time_pulse_us(_echo, 1, timeout_us)
        if duration <= 0:
            return None

        distance_cm = duration * SPEED_OF_SOUND_CM_US
        if 2 <= distance_cm <= 400:
            return distance_cm
    except Exception as e:
        log("ultrasonic", "blocking read error: {}".format(e))
    return None


def _smooth_distance(raw_distance):
    """Light smoothing: blend with last good value to reduce jitter."""
    global _last_good_distance_cm
    if _last_good_distance_cm is None:
        _last_good_distance_cm = raw_distance
    else:
        _last_good_distance_cm = (_last_good_distance_cm * 0.7) + (raw_distance * 0.3)
    return round(_last_good_distance_cm, 2)


def read_ultrasonic():
    global _last_read_ms, _measurement_pending, _measurement_ready, _echo_duration
    global _measurement_count, _failed_measurements, _trigger_time_ms
    global _consecutive_timeouts, _timeout_log_counter, _distance_log_counter
    
    if _trig is None or _echo is None:
        return

    now = ticks_ms()
    if ticks_diff(now, _last_read_ms) < READ_INTERVAL_MS:
        return

    _last_read_ms = now

    if _measurement_pending:
        # Still waiting for previous measurement
        # Check timeout (>50ms = no echo received, max 400cm = ~23ms)
        if ticks_diff(now, _trigger_time_ms) > 50:
            # log("ultrasonic", "⚠️  Measurement timeout - no echo received")
            _measurement_pending = False
            _failed_measurements += 1
            _consecutive_timeouts += 1
            # Try a simple blocking read after a few consecutive misses to keep data flowing
            if _consecutive_timeouts >= 3:
                fallback = _blocking_single_read()
                _consecutive_timeouts = 0
                if fallback is not None:
                    blended = _smooth_distance(fallback)
                    state.sensor_data["ultrasonic_distance_cm"] = blended
                    _distance_log_counter += 1
                    log("ultrasonic", "fallback dist {:.2f} cm (failed total {})".format(blended, _failed_measurements))
                else:
                    state.sensor_data["ultrasonic_distance_cm"] = _last_good_distance_cm
                    _timeout_log_counter += 1
                    log("ultrasonic", "timeout series {} (failed total {})".format(_timeout_log_counter, _failed_measurements))
            else:
                state.sensor_data["ultrasonic_distance_cm"] = _last_good_distance_cm
        return

    if _measurement_ready:
        # Process completed measurement
        duration = _echo_duration
        _measurement_ready = False
        _measurement_count += 1
        
        if duration > 0:
            distance_cm = duration * SPEED_OF_SOUND_CM_US
            
            # Filter out of range measurements (HC-SR04: 2cm - 400cm)
            if 2 <= distance_cm <= 400:
                blended = _smooth_distance(distance_cm)
                state.sensor_data["ultrasonic_distance_cm"] = blended
                _consecutive_timeouts = 0
                # log("ultrasonic", f"✓ Distance: {distance_cm:.2f} cm (duration: {duration}µs)")
                _distance_log_counter += 1
                if _distance_log_counter % 10 == 0:
                    log("ultrasonic", "ok dist {:.2f} cm dur {}us (count {}, failed {})".format(blended, duration, _measurement_count, _failed_measurements))
            else:
                # log("ultrasonic", f"⚠️  Out of range: {distance_cm:.2f} cm")
                state.sensor_data["ultrasonic_distance_cm"] = _last_good_distance_cm
                _failed_measurements += 1
        else:
            # log("ultrasonic", "⚠️  Invalid duration (0)")
            state.sensor_data["ultrasonic_distance_cm"] = _last_good_distance_cm
            _failed_measurements += 1
        
        # Log statistics periodically (disabled for unified logging)
        # if _measurement_count % 20 == 0:
        #     success_rate = ((_measurement_count - _failed_measurements) / _measurement_count * 100) if _measurement_count > 0 else 0
        #     log("ultrasonic", f"📊 Stats: {_measurement_count} measurements, {_failed_measurements} failed ({success_rate:.1f}% success)")
        
        return

    # Start new measurement
    try:
        _measurement_pending = True
        _trigger_time_ms = now  # Salva il tempo di inizio della misurazione
        _echo_start_time = 0
        _echo_duration = 0
        # Send trigger pulse (10us minimo, 20us per sicurezza)
        _trig.value(0)
        sleep_us(2)
        _trig.value(1)
        sleep_us(20)
        _trig.value(0)
    except Exception as e:
        log("ultrasonic", f"❌ Trigger error: {e}")
        _measurement_pending = False
        _failed_measurements += 1
        state.sensor_data["ultrasonic_distance_cm"] = None


# Note: any blocking diagnostics removed to honor non-blocking policy

