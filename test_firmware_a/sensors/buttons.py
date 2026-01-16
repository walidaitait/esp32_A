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
_button_enabled = {}  # Track which buttons are enabled

def init_buttons():
    global _buttons, _last_state, _button_enabled
    try:
        # Build enabled flags map
        _button_enabled = {
            'b1': config.BUTTON_B1_ENABLED,
            'b2': config.BUTTON_B2_ENABLED,
            'b3': config.BUTTON_B3_ENABLED
        }
        
        # Only initialize enabled buttons
        _buttons = {}
        for name, pin in config.BUTTON_PINS.items():
            if _button_enabled.get(name, False):
                _buttons[name] = Pin(pin, Pin.IN, Pin.PULL_UP)
                log("sensor.buttons", "Button {} enabled on pin {}".format(name, pin))
            else:
                log("sensor.buttons", "Button {} disabled (skipping init)".format(name))
        
        if not _buttons:
            log("sensor.buttons", "No buttons enabled")
            return True
        
        # Wait for pins to stabilize
        sleep_ms(50)
        
        # Log raw pin values
        log("sensor.buttons", "init_buttons: Raw pin values after stabilization")
        for name, pin in _buttons.items():
            log("sensor.buttons", "init_buttons: {} = {}".format(name, pin.value()))
        
        # Initialize state based on actual pin readings
        # Wiring as used on board A: pin HIGH (1) = pressed, pin LOW (0) = not pressed
        _last_state = {name: pin.value() == 1 for name, pin in _buttons.items()}
        
        # Update global state to match actual button state (only for enabled buttons)
        for name, pressed in _last_state.items():
            state.button_state[name] = pressed
        
        log("sensor.buttons", "init_buttons: {} button(s) initialized".format(len(_buttons)))
        return True
    except Exception as e:
        log("sensor.buttons", "init_buttons: Initialization failed: {}".format(e))
        _buttons = {}
        _last_state = {}
        _button_enabled = {}
        return False

def read_buttons():
    if not _buttons:
        return
    if not elapsed("buttons", config.BUTTON_INTERVAL):
        return
    try:
        for name, pin in _buttons.items():
            # Wiring as used on board A: HIGH (1) = pressed, LOW (0) = not pressed
            pressed = pin.value() == 1
            if pressed != _last_state[name]:
                _last_state[name] = pressed
                state.button_state[name] = pressed
                log("sensor.buttons", "read_buttons: Button {} {}".format(name, "pressed" if pressed else "released"))
            else:
                state.button_state[name] = pressed
    except Exception as e:
        log("sensor.buttons", "read_buttons: Read error: {}".format(e))
