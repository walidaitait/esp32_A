"""SG90 9g Servo motor driver for ESP32-B automatic gate control.

Imported by: core.actuator_loop
Imports: machine (Pin, PWM), time, config.config, core.state, debug.debug

Controls SG90 servo for automatic gate opening/closing based on:
1. Presence detection from ultrasonic sensor (Board A)
2. Alarm level from alarm logic (Board A)

Gate automation logic (SECURITY ENHANCED):
- presence_detected=True + alarm_level="danger" → Open gate (90°)
- presence lost for 5s → Close gate (0°)
- Manual control via commands overrides automation temporarily

SECURITY: Gate only opens automatically in "danger" mode to prevent
unauthorized entry (e.g., burglar triggering ultrasonic sensor).

Servo control features:
- Smooth motion: Moves at configurable speed (default 2°/50ms = ~40°/s)
- PWM parameters: 50Hz, 0.5-2.5ms pulse width, 0-180° range
- Non-blocking: Updates called from actuator_loop every 100ms

Hardware: SG90 servo on GPIO configured in config.SERVO_PIN
"""
from machine import Pin, PWM  # type: ignore
from time import ticks_ms, ticks_diff  # type: ignore
from config import config
from core import state
from debug.debug import log

_pwm = None
_angle = 0
_initialized = False
_target_angle = 0
_moving = False
_last_update = 0
_move_speed = 2  # Degrees per 50ms update cycle (max ~90°/s)

# Gate automation state (received from ESP32-A)
_presence_detected = False
_gate_open = False
_presence_lost_time_ms = None

# Typical PWM parameters for servo: 50Hz, pulse 0.5-2.5ms
_PWM_FREQ = 50
_MIN_US = 500
_MAX_US = 2500
_PERIOD_US = 1000000 // _PWM_FREQ
_MAX_DUTY = 1023


def _angle_to_duty(angle):
    # Map 0-180° to 10-bit duty (0-1023)
    angle = max(0, min(180, angle))
    pulse_us = _MIN_US + ((_MAX_US - _MIN_US) * angle) // 180
    duty_10bit = (_MAX_DUTY * pulse_us) // _PERIOD_US
    # Convert to 16-bit for duty_u16()
    duty_16bit = duty_10bit * 64
    log("actuator.servo", "_angle_to_duty angle={} -> pulse_us={} -> duty_10bit={} -> duty_u16={}".format(angle, pulse_us, duty_10bit, duty_16bit))
    return duty_16bit


def _set_angle_immediate(angle):
    """Set servo angle directly (internal use)."""
    global _angle
    if _pwm is None:
        log("actuator.servo", "_set_angle_immediate ignored (PWM not initialized)")
        return
    
    _angle = max(0, min(config.SERVO_MAX_ANGLE, angle))
    try:
        duty_val = _angle_to_duty(_angle)
        _pwm.duty_u16(duty_val)
        log("actuator.servo", "_set_angle_immediate duty_u16({})={}".format(_angle, duty_val))
        state.actuator_state["servo"]["angle"] = _angle
    except Exception as e:
        log("actuator.servo", "Set angle error: {}".format(e))


def set_servo_angle(angle):
    """Set servo target angle (moves smoothly to target)."""
    global _target_angle, _moving, _last_update
    
    if _pwm is None:
        log("actuator.servo", "set_servo_angle ignored (PWM not initialized)")
        return
    
    # Limit to allowed range
    angle = max(0, min(config.SERVO_MAX_ANGLE, angle))
    log("actuator.servo", "set_servo_angle target={}".format(angle))
    _target_angle = angle
    _moving = True
    _last_update = ticks_ms()
    
    # Mark as moving in state
    state.actuator_state["servo"]["moving"] = True


def set_servo_angle_immediate(angle):
    """Set servo angle instantly (no smoothing)."""
    global _target_angle, _moving

    if _pwm is None:
        log("actuator.servo", "set_servo_angle_immediate ignored (PWM not initialized)")
        return

    angle = max(0, min(config.SERVO_MAX_ANGLE, angle))
    _target_angle = angle
    _moving = False
    state.actuator_state["servo"]["moving"] = False
    _set_angle_immediate(angle)
    log("actuator.servo", "set_servo_angle_immediate angle={}".format(angle))


def _update_servo_smooth():
    """Update servo angle smoothly (call periodically)."""
    global _angle, _moving, _target_angle, _last_update
    
    if _pwm is None or not _moving:
        return
    log("actuator.servo", "_update_servo_smooth angle={} target={} moving={}".format(_angle, _target_angle, _moving))
    
    now = ticks_ms()
    elapsed = ticks_diff(now, _last_update)
    
    # Update every 50ms (20Hz update rate)
    if elapsed < 50:
        return
    
    _last_update = now
    
    # Calculate delta
    delta = _target_angle - _angle
    
    if delta == 0:
        # Reached target
        _moving = False
        state.actuator_state["servo"]["moving"] = False
        return
    
    # Move towards target at _move_speed degrees per cycle
    if abs(delta) <= _move_speed:
        # Close enough, snap to target
        _set_angle_immediate(_target_angle)
        _moving = False
        state.actuator_state["servo"]["moving"] = False
    else:
        # Move one step towards target
        if delta > 0:
            new_angle = _angle + _move_speed
        else:
            new_angle = _angle - _move_speed
        _set_angle_immediate(new_angle)


def init_servo():
    global _pwm, _angle, _target_angle, _initialized
    log("actuator.servo", "init_servo() called")
    try:
        servo_pin = config.SERVO_PIN
        log("actuator.servo", "init_servo: SERVO_PIN={}".format(servo_pin))
        pin = Pin(servo_pin, Pin.OUT)
        log("actuator.servo", "init_servo: Pin object created")
        _pwm = PWM(pin, freq=_PWM_FREQ)
        log("actuator.servo", "init_servo: PWM created freq={}Hz, PWM object={}".format(_PWM_FREQ, _pwm))

        # Start always at 0°
        _angle = 0
        _target_angle = 0
        state.actuator_state["servo"]["angle"] = 0
        state.actuator_state["servo"]["moving"] = False

        # Mark initialized before first duty set so guard does not block
        _initialized = True
        log("actuator.servo", "init_servo: about to call _set_angle_immediate(0)")
        _set_angle_immediate(_angle)
        state.actuator_state["servo"]["moving"] = False

        log("actuator.servo", "Servo initialized at 0° (smooth movement enabled)")
        return True
    except Exception as e:
        log("actuator.servo", "Initialization failed: {}".format(e))
        import traceback
        log("actuator.servo", "Traceback: {}".format(traceback.format_exc()))
        _pwm = None
        _initialized = False
        return False


def update_servo_test():
    """Update servo: handle smooth movement."""
    _update_servo_smooth()


def update_gate_automation():
    """Update gate based on presence detection from ESP32-A (called from main loop).
    
    SECURITY ENHANCEMENT: Gate only opens automatically if:
    1. Presence is detected (distance < threshold)
    2. System is in DANGER mode (alarm_level == "danger")
    
    In NORMAL or WARNING modes, presence_detected remains True but servo does not open.
    """
    global _presence_detected, _gate_open, _presence_lost_time_ms, _target_angle
    
    if _pwm is None:
        return
    
    # Read presence state and alarm level from received sensor data
    presence = state.received_sensor_state.get("presence_detected", False)
    alarm_level = state.received_sensor_state.get("alarm_level", "normal")
    
    # SECURITY CHECK: Only allow automatic gate opening in DANGER mode
    # In NORMAL or WARNING modes, presence flag stays True but gate does NOT open
    allow_auto_open = (alarm_level == "danger")
    
    # State change: presence detected in DANGER mode -> open gate
    if presence and allow_auto_open and not _gate_open:
        _gate_open = True
        _presence_lost_time_ms = None
        set_servo_angle(90)  # Open gate
        log("actuator.servo.gate", "Gate: presence detected in DANGER mode, opening...")
    
    # Presence detected but NOT in danger mode -> keep gate closed (do not open)
    elif presence and not allow_auto_open and not _gate_open:
        # Presence is detected but system is in normal/warning mode
        # Log this security action for monitoring
        log("actuator.servo.gate", "Gate: presence detected but in {} mode (not opening)".format(alarm_level))
        pass
    
    # Presence still active in danger mode -> keep gate open
    elif presence and allow_auto_open and _gate_open:
        # Gate already open and presence still detected, nothing to do
        pass
    
    # Presence lost OR not in danger mode -> start countdown to close
    elif (not presence or not allow_auto_open) and _gate_open:
        if _presence_lost_time_ms is None:
            if not presence:
                log("actuator.servo.gate", "Gate: presence lost, countdown to close started")
            else:
                log("actuator.servo.gate", "Gate: system left DANGER mode, countdown to close started")
            _presence_lost_time_ms = ticks_ms()
        else:
            # Check if delay has elapsed
            close_delay_ms = getattr(config, "GATE_CLOSE_DELAY_MS", 10000)
            elapsed = ticks_diff(ticks_ms(), _presence_lost_time_ms)
            
            if elapsed >= close_delay_ms:
                # Close gate
                _gate_open = False
                _presence_lost_time_ms = None
                set_servo_angle(0)  # Close gate
                log("actuator.servo.gate", "Gate: closing after delay ({} ms)".format(close_delay_ms))
    
    # No presence and gate already closed -> nothing to do
    else:
        pass
    
    _presence_detected = presence
