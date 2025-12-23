from machine import Pin, PWM  # type: ignore
import config, state
from timers import elapsed
from debug import log

_pwm = None
_angle = 0
_direction = 1
_initialized = False

# Parametri PWM tipici per servo: 50Hz, impulso 0.5-2.5ms
_PWM_FREQ = 50
_MIN_US = 500
_MAX_US = 2500
_PERIOD_US = 1000000 // _PWM_FREQ
_MAX_DUTY = 1023


def _angle_to_duty(angle):
    # Map 0-180° a un duty 10bit
    angle = max(0, min(180, angle))
    pulse_us = _MIN_US + ((_MAX_US - _MIN_US) * angle) // 180
    duty = (_MAX_DUTY * pulse_us) // _PERIOD_US
    return duty


def init_servo():
    global _pwm, _angle, _direction, _initialized
    try:
        pin = Pin(config.SERVO_PIN, Pin.OUT)
        _pwm = PWM(pin, freq=_PWM_FREQ)
        _angle = config.SERVO_MIN_ANGLE
        _direction = 1
        _pwm.duty(_angle_to_duty(_angle))
        state.actuator_state["servo"]["angle"] = _angle
        state.actuator_state["servo"]["moving"] = True
        _initialized = True
        log("servo", "Servo initialized")
        return True
    except Exception as e:
        print("[servo] Initialization failed:", e)
        _pwm = None
        _initialized = False
        return False


def update_servo_test():
    """Sweep non bloccante tra SERVO_MIN_ANGLE e SERVO_MAX_ANGLE."""
    global _angle, _direction
    if not _initialized or not config.SERVO_TEST_ENABLED:
        return

    if not elapsed("servo_step", config.SERVO_STEP_INTERVAL_MS):
        return

    _angle += _direction * config.SERVO_STEP_DEG
    if _angle >= config.SERVO_MAX_ANGLE:
        _angle = config.SERVO_MAX_ANGLE
        _direction = -1
    elif _angle <= config.SERVO_MIN_ANGLE:
        _angle = config.SERVO_MIN_ANGLE
        _direction = 1

    try:
        _pwm.duty(_angle_to_duty(_angle))
        state.actuator_state["servo"]["angle"] = _angle
        state.actuator_state["servo"]["moving"] = True
    except Exception as e:
        log("servo", "Update error: {}".format(e))
        state.actuator_state["servo"]["moving"] = False
