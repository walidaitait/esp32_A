from machine import Pin  # type: ignore
import config, state
from timers import elapsed
from debug import log
import time

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
        time.sleep_ms(50)
        
        # Debug: print raw pin values
        print("[buttons] Raw pin values after stabilization:")
        for name, pin in _buttons.items():
            print(f"  {name}: {pin.value()}")
        
        # Initialize state based on actual pin readings
        # Con PULL_UP: pin.value() == 1 quando NON premuto, 0 quando premuto
        # MA se i moduli DFRobot hanno logica diversa, potrebbe essere invertito
        # Proviamo entrambe le logiche e vediamo quale funziona
        _last_state = {name: pin.value() == 1 for name, pin in _buttons.items()}  # INVERTITO: 1 = premuto
        
        # Update global state to match actual button state
        for name, pressed in _last_state.items():
            state.button_state[name] = pressed
        
        log("buttons", "Buttons initialized (inverted logic: HIGH=pressed)")
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
            # INVERTITO: Con moduli DFRobot, HIGH = premuto, LOW = non premuto
            pressed = pin.value() == 1
            if pressed != _last_state[name]:
                _last_state[name] = pressed
                state.button_state[name] = pressed
                log("buttons", f"Button {name} {'pressed' if pressed else 'released'}")
            else:
                state.button_state[name] = pressed
    except Exception as e:
        log("buttons", f"Read error: {e}")
