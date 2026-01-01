from machine import Pin, PWM  # type: ignore
from config import config
from core import state
from debug.debug import log

_pwm = None
_angle = 0
_initialized = False

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


def set_servo_angle(angle):
    """Set servo angle (non-blocking)."""
    global _angle
    if not _initialized or _pwm is None:
        return

    # Limit to allowed range and save
    angle = max(0, min(config.SERVO_MAX_ANGLE, angle))
    _angle = angle

    try:
        _pwm.duty(_angle_to_duty(_angle))
        state.actuator_state["servo"]["angle"] = _angle
    except Exception as e:
        log("servo", "Set angle error: {}".format(e))


def init_servo():
    global _pwm, _angle, _initialized
    try:
        servo_pin = 23  # GPIO23
        pin = Pin(servo_pin, Pin.OUT)
        _pwm = PWM(pin, freq=_PWM_FREQ)

        # Start always at 0°
        _angle = 0

        set_servo_angle(_angle)
        state.actuator_state["servo"]["moving"] = False

        _initialized = True
        log("servo", "Servo initialized at 0°")
        return True
    except Exception as e:
        log("servo", "Initialization failed: {}".format(e))
        _pwm = None
        _initialized = False
        return False




def update_servo_test():
    """Placeholder per futuri test del servo."""
    pass
