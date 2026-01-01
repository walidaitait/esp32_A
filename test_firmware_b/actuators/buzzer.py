from machine import Pin, PWM  # type: ignore
from core import state
from debug.debug import log

_pwm = None
_initialized = False


def set_tone(freq):
    """Set a continuous frequency (0 = silence) non-blocking mode.

    Used by both buzzer internal test and integrated servo test.
    """
    global _pwm

    if not _initialized or _pwm is None:
        return

    try:
        if freq > 0:
            try:
                _pwm.freq(freq)
            except Exception as e:
                log("buzzer", "freq set error: {}".format(e))
            _pwm.duty(512)
            state.actuator_state["buzzer"]["active"] = True
        else:
            _pwm.duty(0)
            state.actuator_state["buzzer"]["active"] = False
    except Exception as e:
        log("buzzer", "PWM error: {}".format(e))


def init_buzzer():
    global _pwm, _initialized
    try:
        buzzer_pin = 25  # GPIO25
        pin = Pin(buzzer_pin, Pin.OUT)
        # Frequenza iniziale arbitraria
        _pwm = PWM(pin, freq=1000)
        _pwm.duty(0)

        state.actuator_state["buzzer"]["active"] = False
        _initialized = True

        log("buzzer", "Passive buzzer initialized on GPIO{}".format(buzzer_pin))
        return True
    except Exception as e:
        log("buzzer", "Initialization failed: {}".format(e))
        _pwm = None
        _initialized = False
        return False




def update_buzzer_test():
    """Placeholder for future buzzer tests."""
    pass
