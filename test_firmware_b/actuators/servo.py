from machine import Pin, PWM  # type: ignore
import config, state
from timers import elapsed
from debug import log
from actuators import leds, buzzer

_pwm = None
_angle = 0
_direction = 1
_initialized = False

# Stato logico del movimento: "idle", "forward", "backward"
_motion_state = "idle"

# Sequenza LED per il test integrato
_led_index = 0

# Parametri PWM tipici per servo: 50Hz, impulso 0.5-2.5ms
_PWM_FREQ = 50
_MIN_US = 500
_MAX_US = 2500
_PERIOD_US = 1000000 // _PWM_FREQ
_MAX_DUTY = 1023

# Attesa tra un ciclo completo (0 -> max -> 0) e il successivo
_SWEEP_DELAY_MS = 5000

# Melodia: frequenza proporzionale all'angolo (basso all'inizio,
# piu alta a fine corsa). All'andata i toni crescono, al ritorno
# decrescono automaticamente perche l'angolo diminuisce.
_BUZZER_MIN_FREQ = 800
_BUZZER_MAX_FREQ = 2000


def _angle_to_duty(angle):
    # Map 0-180° a un duty 10bit
    angle = max(0, min(180, angle))
    pulse_us = _MIN_US + ((_MAX_US - _MIN_US) * angle) // 180
    duty = (_MAX_DUTY * pulse_us) // _PERIOD_US
    return duty


def set_servo_angle(angle):
    """Imposta l'angolo del servo (non bloccante)."""
    global _angle
    if not _initialized or _pwm is None:
        return

    # Limita all'intervallo consentito e salva
    angle = max(0, min(config.SERVO_MAX_ANGLE, angle))
    _angle = angle

    try:
        _pwm.duty(_angle_to_duty(_angle))
        state.actuator_state["servo"]["angle"] = _angle
    except Exception as e:
        log("servo", "Set angle error: {}".format(e))


def init_servo():
    global _pwm, _angle, _direction, _initialized, _motion_state
    try:
        pin = Pin(config.SERVO_PIN, Pin.OUT)
        _pwm = PWM(pin, freq=_PWM_FREQ)

        # Richiesta: partire sempre da 0°
        _angle = 0
        _direction = 1
        _motion_state = "idle"

        set_servo_angle(_angle)
        state.actuator_state["servo"]["moving"] = False

        _initialized = True
        log("servo", "Servo initialized at 0°")
        return True
    except Exception as e:
        print("[servo] Initialization failed:", e)
        _pwm = None
        _initialized = False
        return False


def _update_led_sequence():
    """Accende un LED alla volta in sequenza ciclica durante il movimento."""
    global _led_index

    names = list(config.LED_PINS.keys())
    if not names:
        return

    if _led_index >= len(names):
        _led_index = 0

    current = names[_led_index]

    # Un solo LED acceso alla volta
    for name in names:
        if name == current:
            leds.set_led_state(name, "on")
        else:
            leds.set_led_state(name, "off")

    _led_index = (_led_index + 1) % len(names)


def _update_buzzer_tone_for_angle():
    """Imposta un tono in funzione dell'angolo corrente.

    - All'andata (0 -> max) i toni crescono.
    - Al ritorno (max -> 0) i toni decrescono.
    Non viene eseguita alcuna sequenza ciclica: la frequenza dipende
    solo dall'angolo istantaneo del servo.
    """
    if not config.BUZZER_TEST_ENABLED:
        return

    try:
        if config.SERVO_MAX_ANGLE <= 0:
            buzzer.set_tone(0)
            return

        # Normalizza l'angolo nell'intervallo [0, 1]
        ratio = max(0, min(1, _angle / config.SERVO_MAX_ANGLE))
        freq_span = _BUZZER_MAX_FREQ - _BUZZER_MIN_FREQ
        freq = int(_BUZZER_MIN_FREQ + freq_span * ratio)

        buzzer.set_tone(freq)
    except Exception:
        # In caso il modulo buzzer non sia disponibile o inizializzato
        pass


def _stop_effects():
    """Ferma melodia e spegne tutti i LED."""
    global _led_index

    _led_index = 0

    # Spegni buzzer
    try:
        buzzer.set_tone(0)
    except Exception:
        pass

    # Spegni tutti i LED
    for name in config.LED_PINS.keys():
        leds.set_led_state(name, "off")


def update_servo_test():
    """Test integrato servo + LED + buzzer.

    Ogni 5 secondi il servo effettua uno sweep 0 -> max -> 0.
    Durante il movimento:
      - i LED si accendono uno alla volta in sequenza ciclica
      - il buzzer esegue una melodia a toni crescenti in andata
        e decrescenti in ritorno.
    Tutta la logica e non bloccante.
    """
    global _angle, _direction, _motion_state

    if not _initialized or not config.SERVO_TEST_ENABLED:
        return

    # Stato fermo: attendi 5s tra un ciclo completo e il successivo
    if _motion_state == "idle":
        if not elapsed("servo_sweep_delay", _SWEEP_DELAY_MS):
            return

        # Avvia nuovo sweep da 0° verso l'angolo massimo
        _angle = 0
        _direction = 1
        _motion_state = "forward"
        set_servo_angle(_angle)
        state.actuator_state["servo"]["moving"] = True

        _update_led_sequence()
        _update_buzzer_tone_for_angle()
        return

    # Movimento in corso (forward/backward)
    if not elapsed("servo_step", config.SERVO_STEP_INTERVAL_MS):
        return

    _angle += _direction * config.SERVO_STEP_DEG

    # Gestione inversioni ai limiti
    if _direction > 0 and _angle >= config.SERVO_MAX_ANGLE:
        _angle = config.SERVO_MAX_ANGLE
        set_servo_angle(_angle)
        _direction = -1
        _motion_state = "backward"
    elif _direction < 0 and _angle <= 0:
        # Fine ciclo: torna a 0°, ferma tutto e rientra in idle
        _angle = 0
        set_servo_angle(_angle)
        state.actuator_state["servo"]["moving"] = False
        _motion_state = "idle"
        _stop_effects()
        return
    else:
        set_servo_angle(_angle)

    # Aggiorna effetti sincronizzati al passo del servo
    _update_led_sequence()
    _update_buzzer_tone_for_angle()
