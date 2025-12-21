from machine import Pin  # type: ignore
import config, state
from timers import elapsed
from debug import log
from logic import hooks

_buttons = {}
_last_state = {}

def init_buttons():
    global _buttons, _last_state
    try:
        _buttons = {
            name: Pin(pin, Pin.IN, Pin.PULL_UP)
            for name, pin in config.BUTTON_PINS.items()
        }
        _last_state = {name: False for name in config.BUTTON_PINS.keys()}
        log("buttons", "Buttons initialized")
        return True
    except Exception as e:
        print(f"[buttons] Initialization failed: {e}")
        print("[buttons] Sensor disabled - system will continue without button monitoring")
        _buttons = {}
        _last_state = {}
        return False

def read_buttons():
    if not _buttons:
        return
    if not elapsed("buttons", config.BUTTON_INTERVAL):
        return
    try:
        for name, pin in _buttons.items():
            pressed = not pin.value()
            if pressed != _last_state[name]:
                _last_state[name] = pressed
                state.button_state[name] = pressed
                if pressed:
                    hooks.on_button_triggered(name)
                else:
                    hooks.on_button_released(name)
            else:
                state.button_state[name] = pressed
    except Exception as e:
        log("buttons", f"Read error: {e}")

