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
_measurement_count = 0
_failed_measurements = 0


def init_ultrasonic():
    global _trig, _echo
    try:
        _trig = Pin(ULTRASONIC_TRIG_PIN, Pin.OUT)
        _echo = Pin(ULTRASONIC_ECHO_PIN, Pin.IN)
        _trig.value(0)
        # Set up interrupt for echo pin
        _echo.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_echo_interrupt)
        log("ultrasonic", "Ultrasonic sensor initialized (non-blocking)")
        return True
    except Exception as e:
        print(f"[ultrasonic] Initialization failed: {e}")
        print("[ultrasonic] Sensor disabled - system will continue without ultrasonic monitoring")
        _trig = None
        _echo = None
        return False


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
    global _measurement_count, _failed_measurements
    
    if _trig is None or _echo is None:
        return

    now = time.ticks_ms()
    if time.ticks_diff(now, _last_read_ms) < READ_INTERVAL_MS:
        return

    _last_read_ms = now

    if _measurement_pending:
        # Still waiting for previous measurement
        # Check timeout (>30ms = no echo received)
        if time.ticks_diff(now, _last_read_ms) > 30:
            log("ultrasonic", "⚠️  Measurement timeout - no echo received")
            _measurement_pending = False
            _failed_measurements += 1
            state.sensor_data["ultrasonic_distance_cm"] = None
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
                state.sensor_data["ultrasonic_distance_cm"] = round(distance_cm, 2)
                log("ultrasonic", f"✓ Distance: {distance_cm:.2f} cm (duration: {duration}µs)")
            else:
                log("ultrasonic", f"⚠️  Out of range: {distance_cm:.2f} cm")
                state.sensor_data["ultrasonic_distance_cm"] = None
                _failed_measurements += 1
        else:
            log("ultrasonic", "⚠️  Invalid duration (0)")
            state.sensor_data["ultrasonic_distance_cm"] = None
            _failed_measurements += 1
        
        # Log statistics periodically
        if _measurement_count % 20 == 0:
            success_rate = ((_measurement_count - _failed_measurements) / _measurement_count * 100) if _measurement_count > 0 else 0
            log("ultrasonic", f"📊 Stats: {_measurement_count} measurements, {_failed_measurements} failed ({success_rate:.1f}% success)")
        
        return

    # Start new measurement
    try:
        _measurement_pending = True
        _echo_start_time = 0
        _echo_duration = 0
        # Send trigger pulse (10us minimo, 20us per sicurezza)
        _trig.value(0)
        time.sleep_us(2)
        _trig.value(1)
        time.sleep_us(20)
        _trig.value(0)
    except Exception as e:
        log("ultrasonic", f"❌ Trigger error: {e}")
        _measurement_pending = False
        _failed_measurements += 1
        state.sensor_data["ultrasonic_distance_cm"] = None
