from machine import Pin  # type: ignore
import time
from core import state
from debug.debug import log

_led_pins = {}
_led_order = []
_initialized = False

# State for each LED: mode (off/on/blinking) and blinking parameters
_led_runtime = {}


def init_leds():
    global _led_pins, _led_order, _initialized, _led_runtime
    try:
        _led_pins = {}
        _led_order = []
        _led_runtime = {}
        # Ensure modes dictionary exists in state
        if "led_modes" not in state.actuator_state:
            state.actuator_state["led_modes"] = {}

        # Define LED pins directly
        led_pins = {
            "green": 16,   # GPIO16
            "blue": 17,    # GPIO17
            "red": 19,     # GPIO19
        }

        for name, gpio in led_pins.items():
            p = Pin(gpio, Pin.OUT)
            p.value(0)
            _led_pins[name] = p
            _led_order.append(name)

            # Initial state: off
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
        log("leds", "Initialization failed: {}".format(e))
        _initialized = False
        return False


def _all_off():
    """Turn off all LEDs and reset internal state."""
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
    """Set the state of a single LED.

    mode: "off", "on" or "blinking".
    - blink_interval_ms: total period of blinking cycle (ms).
    - on_duration_ms: duration of ON pulse within the cycle (ms).
    - total_duration_ms: total duration of blinking (ms) before
      automatically returning to OFF state.

    The function is non-blocking: it only updates parameters; the actual
    update is handled in _update_led_runtime() called from the loop.
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




def update_led_test():
    """Handle non-blocking blinking based on _led_runtime."""
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
                    # Blinking ended: return to OFF
                    r["mode"] = "off"
                    r["on"] = False
                    pin.value(0)
                    state.actuator_state["leds"][name] = False
                    if "led_modes" in state.actuator_state:
                        state.actuator_state["led_modes"][name] = "off"
                    continue

            cycle_elapsed = time.ticks_diff(now, r["cycle_start_ms"])
            if cycle_elapsed < 0:
                # Possible counter wrap
                r["cycle_start_ms"] = now
                cycle_elapsed = 0

            if cycle_elapsed >= r["blink_interval"]:
                # New cycle
                r["cycle_start_ms"] = now
                cycle_elapsed = 0

            should_on = cycle_elapsed < r["on_duration"]
            if should_on != r["on"]:
                r["on"] = should_on
                pin.value(1 if should_on else 0)
                state.actuator_state["leds"][name] = should_on