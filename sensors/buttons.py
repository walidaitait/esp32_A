from machine import Pin
import config, state
from timers import elapsed
from debug import log

_buttons = {
    name: Pin(pin, Pin.IN, Pin.PULL_UP)
    for name, pin in config.BUTTON_PINS.items()
}

def read_buttons():
    if not elapsed("buttons", config.BUTTON_INTERVAL):
        return
    for name, pin in _buttons.items():
        state.button_state[name] = not pin.value()

