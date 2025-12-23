from machine import Pin  # type: ignore
import config, state
from timers import elapsed
from debug import log

_led_pins = {}
_led_order = []
_current_index = 0
_initialized = False


def init_leds():
    global _led_pins, _led_order, _initialized
    try:
        _led_pins = {}
        _led_order = []
        for name, gpio in config.LED_PINS.items():
            p = Pin(gpio, Pin.OUT)
            p.value(0)
            _led_pins[name] = p
            _led_order.append(name)
            state.actuator_state["leds"][name] = False
        _initialized = True
        log("leds", "LED modules initialized")
        return True
    except Exception as e:
        print("[leds] Initialization failed:", e)
        _initialized = False
        return False


def _all_off():
    for name, pin in _led_pins.items():
        pin.value(0)
        state.actuator_state["leds"][name] = False


def update_led_test():
    """Test non bloccante: accende ciclicamente un LED alla volta."""
    global _current_index
    if not _initialized or not config.LED_TEST_ENABLED:
        return

    if not elapsed("leds_step", config.LED_STEP_INTERVAL_MS):
        return

    if not _led_order:
        return

    _all_off()
    name = _led_order[_current_index]
    pin = _led_pins[name]
    pin.value(1)
    state.actuator_state["leds"][name] = True

    _current_index = (_current_index + 1) % len(_led_order)
