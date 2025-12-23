from machine import Pin, PWM  # type: ignore
import config, state
from timers import elapsed
from debug import log

_pwm = None
_on = False
_initialized = False

_BUZZER_FREQ = 2000  # Hz


def init_buzzer():
    global _pwm, _on, _initialized
    try:
        pin = Pin(config.BUZZER_PIN, Pin.OUT)
        _pwm = PWM(pin, freq=_BUZZER_FREQ)
        _pwm.duty(0)
        _on = False
        state.actuator_state["buzzer"]["active"] = False
        _initialized = True
        log("buzzer", "Passive buzzer initialized")
        return True
    except Exception as e:
        print("[buzzer] Initialization failed:", e)
        _pwm = None
        _initialized = False
        return False


def update_buzzer_test():
    """Beep ON/OFF non bloccante."""
    global _on
    if not _initialized or not config.BUZZER_TEST_ENABLED:
        return

    if not elapsed("buzzer_toggle", config.BUZZER_TOGGLE_INTERVAL_MS):
        return

    _on = not _on
    if _on:
        _pwm.duty(512)
        state.actuator_state["buzzer"]["active"] = True
    else:
        _pwm.duty(0)
        state.actuator_state["buzzer"]["active"] = False
