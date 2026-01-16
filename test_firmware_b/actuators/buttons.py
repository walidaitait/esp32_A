"""Button input module for ESP32-B.

Reads button states with debouncing.
Same functionality as ESP32-A buttons but adapted for actuator board.
"""
from machine import Pin  # type: ignore
from time import sleep_ms  # type: ignore
from config import config
from core import state
from core.timers import elapsed
from debug.debug import log

_button = None
_last_state = False
_button_enabled = False

def init_buttons():
    """Initialize button on ESP32-B."""
    global _button, _last_state, _button_enabled
    try:
        # Check if button is enabled in config
        _button_enabled = config.BUTTON_ENABLED
        
        if not _button_enabled:
            log("actuator.buttons", "Button disabled in config (skipping init)")
            return True
        
        # Initialize button pin with pull-up resistor
        _button = Pin(config.BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        log("actuator.buttons", "Button enabled on pin {}".format(config.BUTTON_PIN))
        
        # Wait for pin to stabilize
        sleep_ms(50)
        
        # Log raw pin value
        log("actuator.buttons", "init_buttons: Raw pin value after stabilization: {}".format(_button.value()))
        
        # Initialize state based on actual pin reading
        # Pull-up wiring: pin HIGH (1) = not pressed, pin LOW (0) = pressed
        # Keep semantic: True => button physically pressed
        _last_state = _button.value() == 1  # True only when pin is LOW (button pressed)
        
        # Update global state
        state.actuator_state["button"] = _last_state
        
        log("actuator.buttons", "init_buttons: Button initialized, current state: {} (True=pressed, False=not pressed)".format(
            _last_state))
        return True
    except Exception as e:
        log("actuator.buttons", "init_buttons: Initialization failed: {}".format(e))
        _button = None
        _button_enabled = False
        return False

def read_buttons():
    """Read button state with debouncing."""
    global _button, _last_state, _button_enabled
    
    if not _button_enabled or _button is None:
        return
    
    if not elapsed("button", config.BUTTON_INTERVAL):
        return
    
    try:
        # Pull-up wiring: pin HIGH (1) = not pressed, pin LOW (0) = pressed
        # Keep semantic: True => button physically pressed
        pressed = _button.value() == 1  # True only when pin is LOW (button pressed)
        
        if pressed != _last_state:
            _last_state = pressed
            state.actuator_state["button"] = pressed
            log("actuator.buttons", "read_buttons: Button {}".format(
                "pressed" if pressed else "released"))
        else:
            state.actuator_state["button"] = pressed
    except Exception as e:
        log("actuator.buttons", "read_buttons: Read error: {}".format(e))

def is_button_enabled():
    """Check if button is enabled."""
    return _button_enabled
