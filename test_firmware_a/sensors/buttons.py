"""Button input module.

Reads button states with debouncing.
"""
from machine import Pin  # type: ignore
from time import sleep_ms  # type: ignore
from config import config
from core import state
from core.timers import elapsed
from debug.debug import log

_buttons = {}
_last_state = {}

def init_buttons():
    global _buttons, _last_state
    try:
        _buttons = {
            name: Pin(pin, Pin.IN, Pin.PULL_UP)
            for name, pin in config.BUTTON_PINS.items()
        }
        # Wait for pins to stabilize
        sleep_ms(50)
        
        # Log raw pin values
        log("buttons", "init_buttons: Raw pin values after stabilization")
        for name, pin in _buttons.items():
            log("buttons", "init_buttons: {} = {}".format(name, pin.value()))
        
        # Initialize state based on actual pin readings
        # With PULL_UP: pin.value() == 1 when NOT pressed, 0 when pressed
        _last_state = {name: pin.value() == 1 for name, pin in _buttons.items()}
        
        # Update global state to match actual button state
        for name, pressed in _last_state.items():
            state.button_state[name] = pressed
        
        log("buttons", "init_buttons: Buttons initialized")
        return True
    except Exception as e:
        log("buttons", "init_buttons: Initialization failed: {}".format(e))
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
            # With PULL_UP: HIGH = not pressed, LOW = pressed
            pressed = pin.value() == 1
            if pressed != _last_state[name]:
                _last_state[name] = pressed
                state.button_state[name] = pressed
                log("buttons", "read_buttons: Button {} {}".format(name, "pressed" if pressed else "released"))
            else:
                state.button_state[name] = pressed
    except Exception as e:
        log("buttons", "read_buttons: Read error: {}".format(e))
