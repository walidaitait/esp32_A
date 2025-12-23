from machine import Pin, PWM  # type: ignore
import time
import config, state
from debug import log

_pwm = None
_initialized = False

# Sequenza di toni per il test non bloccante del buzzer passivo
# freq: frequenza in Hz (0 = silenzio), duration_ms: durata del passo
_PATTERN = [
    {"freq": 800, "duration_ms": 250},
    {"freq": 1200, "duration_ms": 150},
    {"freq": 1600, "duration_ms": 350},
    {"freq": 0, "duration_ms": 200},
    {"freq": 2000, "duration_ms": 450},
    {"freq": 1500, "duration_ms": 300},
    {"freq": 0, "duration_ms": 300},
]

_step_index = 0
_step_start_ms = None


def _apply_step():
    """Applica il passo corrente della sequenza (tono o silenzio)."""
    if _pwm is None or not _PATTERN:
        return

    step = _PATTERN[_step_index]
    set_tone(step["freq"])


def set_tone(freq):
    """Imposta una frequenza continua (0 = silenzio) in modo non bloccante.

    Usato sia dal test interno del buzzer che dal test integrato del servo.
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
    global _pwm, _initialized, _step_index, _step_start_ms
    try:
        pin = Pin(config.BUZZER_PIN, Pin.OUT)
        # Frequenza iniziale arbitraria; verra subito aggiornata da _apply_step()
        _pwm = PWM(pin, freq=1000)
        _pwm.duty(0)

        state.actuator_state["buzzer"]["active"] = False
        _initialized = True

        _step_index = 0
        _step_start_ms = time.ticks_ms()
        _apply_step()

        log("buzzer", "Passive buzzer (3-pin) initialized on GPIO{}".format(config.BUZZER_PIN))
        return True
    except Exception as e:
        print("[buzzer] Initialization failed:", e)
        _pwm = None
        _initialized = False
        return False


def update_buzzer_test():
    """Sequenza di toni non bloccante per il buzzer passivo.

    Usa una piccola macchina a stati basata su time.ticks_ms():
    ad ogni passo viene impostata una frequenza (o il silenzio) con
    una certa durata; il main loop puo convivere con LED, LCD, servo, audio.
    """
    global _step_index, _step_start_ms

    if not _initialized or not config.BUZZER_TEST_ENABLED or _pwm is None:
        return

    if not _PATTERN:
        return

    now = time.ticks_ms()

    # Primo ingresso: avvia la sequenza
    if _step_start_ms is None:
        _step_start_ms = now
        _apply_step()
        return

    step = _PATTERN[_step_index]
    duration = step["duration_ms"]

    if time.ticks_diff(now, _step_start_ms) < duration:
        # Durata non ancora trascorsa: nessun blocco, solo ritorno
        return

    # Passa al passo successivo e applica il nuovo tono/silenzio
    _step_index = (_step_index + 1) % len(_PATTERN)
    _step_start_ms = now
    _apply_step()
