from machine import Pin  # type: ignore
import time
import config, state
from timers import elapsed
from debug import log

_led_pins = {}
_led_order = []
_initialized = False

# Stato per ogni LED: modalita (off/on/blinking) e parametri di blinking
_led_runtime = {}

# Indice per la sequenza di test
_test_step_index = 0


def init_leds():
    global _led_pins, _led_order, _initialized, _led_runtime
    try:
        _led_pins = {}
        _led_order = []
        _led_runtime = {}
        # Assicura che esista il dizionario per le modalita nel state
        if "led_modes" not in state.actuator_state:
            state.actuator_state["led_modes"] = {}

        for name, gpio in config.LED_PINS.items():
            p = Pin(gpio, Pin.OUT)
            p.value(0)
            _led_pins[name] = p
            _led_order.append(name)

            # Stato iniziale: spento
            state.actuator_state["leds"][name] = False
            state.actuator_state["led_modes"][name] = "off"

            _led_runtime[name] = {
                "mode": "off",  # "off", "on", "blinking"
                "blink_interval": 0,
                "on_duration": 0,
                "total_duration": None,
                "start_ms": 0,
                "cycle_start_ms": 0,
                "on": False,
            }

        _initialized = True
        log("leds", "LED modules initialized")
        return True
    except Exception as e:
        print("[leds] Initialization failed:", e)
        _initialized = False
        return False


def _all_off():
    """Spegne tutti i LED e azzera lo stato interno."""
    for name, pin in _led_pins.items():
        pin.value(0)
        state.actuator_state["leds"][name] = False
        if "led_modes" in state.actuator_state:
            state.actuator_state["led_modes"][name] = "off"
        if name in _led_runtime:
            _led_runtime[name]["mode"] = "off"
            _led_runtime[name]["on"] = False


def set_led_state(
    name,
    mode,
    blink_interval_ms=None,
    on_duration_ms=None,
    total_duration_ms=None,
):
    """Imposta lo stato di un singolo LED.

    mode: "off", "on" oppure "blinking".
    - blink_interval_ms: periodo totale del ciclo di blinking (ms).
    - on_duration_ms: durata dell'impulso ON all'interno del ciclo (ms).
    - total_duration_ms: durata complessiva del blinking (ms) prima di
      tornare automaticamente allo stato OFF.

    La funzione non e bloccante: aggiorna solo i parametri; l'aggiornamento
    reale viene gestito in _update_led_runtime() richiamato dal loop.
    """
    if not _initialized:
        return
    if name not in _led_pins:
        return

    now = time.ticks_ms()

    if mode == "off":
        _led_pins[name].value(0)
        state.actuator_state["leds"][name] = False
        if "led_modes" in state.actuator_state:
            state.actuator_state["led_modes"][name] = "off"
        if name in _led_runtime:
            r = _led_runtime[name]
            r["mode"] = "off"
            r["on"] = False
        return

    if mode == "on":
        _led_pins[name].value(1)
        state.actuator_state["leds"][name] = True
        if "led_modes" in state.actuator_state:
            state.actuator_state["led_modes"][name] = "on"
        if name in _led_runtime:
            r = _led_runtime[name]
            r["mode"] = "on"
            r["on"] = True
        return

    if mode == "blinking":
        # Parametri di default se non specificati
        if blink_interval_ms is None:
            blink_interval_ms = 800
        if on_duration_ms is None:
            on_duration_ms = blink_interval_ms // 2

        # Limiti di sicurezza
        if blink_interval_ms <= 0:
            blink_interval_ms = 100
        if on_duration_ms <= 0:
            on_duration_ms = blink_interval_ms // 2
        if on_duration_ms > blink_interval_ms:
            on_duration_ms = blink_interval_ms

        r = _led_runtime.get(name)
        if r is None:
            return

        r["mode"] = "blinking"
        r["blink_interval"] = blink_interval_ms
        r["on_duration"] = on_duration_ms
        r["total_duration"] = total_duration_ms
        r["start_ms"] = now
        r["cycle_start_ms"] = now
        r["on"] = True

        _led_pins[name].value(1)
        state.actuator_state["leds"][name] = True
        if "led_modes" in state.actuator_state:
            state.actuator_state["led_modes"][name] = "blinking"
        return


def _update_led_runtime():
    """Gestisce il blinking non bloccante in base a _led_runtime."""
    if not _initialized:
        return

    now = time.ticks_ms()

    for name, r in _led_runtime.items():
        mode = r["mode"]
        pin = _led_pins.get(name)
        if pin is None:
            continue

        if mode == "off":
            pin.value(0)
            state.actuator_state["leds"][name] = False
            continue

        if mode == "on":
            pin.value(1)
            state.actuator_state["leds"][name] = True
            continue

        if mode == "blinking":
            total = r["total_duration"]
            if total is not None:
                if time.ticks_diff(now, r["start_ms"]) >= total:
                    # Fine blinking: torna OFF
                    r["mode"] = "off"
                    r["on"] = False
                    pin.value(0)
                    state.actuator_state["leds"][name] = False
                    if "led_modes" in state.actuator_state:
                        state.actuator_state["led_modes"][name] = "off"
                    continue

            cycle_elapsed = time.ticks_diff(now, r["cycle_start_ms"])
            if cycle_elapsed < 0:
                # Eventuale wrap del contatore
                r["cycle_start_ms"] = now
                cycle_elapsed = 0

            if cycle_elapsed >= r["blink_interval"]:
                # Nuovo ciclo
                r["cycle_start_ms"] = now
                cycle_elapsed = 0

            should_on = cycle_elapsed < r["on_duration"]
            if should_on != r["on"]:
                r["on"] = should_on
                pin.value(1 if should_on else 0)
                state.actuator_state["leds"][name] = should_on


def update_led_test():
    """Test non bloccante dei 3 LED.

    Usa set_led_state() per assegnare, in sequenza, stati diversi
    (spento, acceso, lampeggiante) ai LED. La funzione viene richiamata
    spesso dal main loop e non contiene sleep bloccanti.
    """
    global _test_step_index

    if not _initialized or not config.LED_TEST_ENABLED:
        return

    # Aggiorna sempre i blinking in base al tempo reale
    _update_led_runtime()

    # Avanza la sequenza solo ad intervalli regolari
    if not elapsed("leds_step", config.LED_STEP_INTERVAL_MS):
        return

    if not _led_order:
        return

    # Sequenza di esempio:
    # 0: Red ON, Blue OFF, Green OFF
    # 1: Red OFF, Blue ON, Green OFF
    # 2: Red OFF, Blue OFF, Green BLINKING
    # 3: Red BLINKING, Blue OFF, Green ON

    if _test_step_index == 0:
        set_led_state("red", "on")
        set_led_state("blue", "off")
        set_led_state("green", "off")
    elif _test_step_index == 1:
        set_led_state("red", "off")
        set_led_state("blue", "on")
        set_led_state("green", "off")
    elif _test_step_index == 2:
        set_led_state("red", "off")
        set_led_state("blue", "off")
        set_led_state(
            "green",
            "blinking",
            blink_interval_ms=800,
            on_duration_ms=300,
            total_duration_ms=None,
        )
    elif _test_step_index == 3:
        set_led_state(
            "red",
            "blinking",
            blink_interval_ms=400,
            on_duration_ms=200,
            total_duration_ms=None,
        )
        set_led_state("blue", "off")
        set_led_state("green", "on")

    _test_step_index = (_test_step_index + 1) % 4

