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

# Typical PWM parameters for servo: 50Hz, pulse 0.5-2.5ms
_PWM_FREQ = 50
_MIN_US = 500
_MAX_US = 2500
_PERIOD_US = 1000000 // _PWM_FREQ
_MAX_DUTY = 1023


def _angle_to_duty(angle):
    # Map 0-180° to 10-bit duty
    angle = max(0, min(180, angle))
    pulse_us = _MIN_US + ((_MAX_US - _MIN_US) * angle) // 180
    duty = (_MAX_DUTY * pulse_us) // _PERIOD_US
    return duty


def _set_angle_immediate(angle):
    """Set servo angle directly (internal use)."""
    global _angle
    if _pwm is None:
        return
    
    _angle = max(0, min(config.SERVO_MAX_ANGLE, angle))
    try:
        _pwm.duty(_angle_to_duty(_angle))
        state.actuator_state["servo"]["angle"] = _angle
    except Exception as e:
        log("servo", "Set angle error: {}".format(e))


def set_servo_angle(angle):
    """Set servo target angle (moves smoothly to target)."""
    global _target_angle, _moving, _last_update
    
    if _pwm is None:
        return
    
    # Limit to allowed range
    angle = max(0, min(config.SERVO_MAX_ANGLE, angle))
    _target_angle = angle
    _moving = True
    _last_update = ticks_ms()
    
    # Mark as moving in state
    state.actuator_state["servo"]["moving"] = True


def _update_servo_smooth():
    """Update servo angle smoothly (call periodically)."""
    global _angle, _moving, _target_angle, _last_update
    
    if _pwm is None or not _moving:
        return
    
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
    try:
        servo_pin = config.SERVO_PIN
        pin = Pin(servo_pin, Pin.OUT)
        _pwm = PWM(pin, freq=_PWM_FREQ)

        # Start always at 0°
        _angle = 0
        _target_angle = 0

        # Mark initialized before first duty set so guard does not block
        _initialized = True
        _set_angle_immediate(_angle)
        state.actuator_state["servo"]["moving"] = False

        log("servo", "Servo initialized at 0° (smooth movement enabled)")
        return True
    except Exception as e:
        log("servo", "Initialization failed: {}".format(e))
        _pwm = None
        _initialized = False
        return False


def update_servo_test():
    """Update servo: handle smooth movement."""
    _update_servo_smooth()
