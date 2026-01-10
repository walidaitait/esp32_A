"""Actuator simulation module for testing.

Provides simulated actuator values without requiring actual hardware.
Used when SIMULATE_ACTUATORS is True in main.py.
"""

from core import state
from debug.debug import log

# Fixed simulated values (can be made dynamic in the future)
SIMULATED_LED_GREEN_MODE = "on"
SIMULATED_LED_BLUE_MODE = "blinking"
SIMULATED_LED_RED_MODE = "off"
SIMULATED_SERVO_ANGLE = 90
SIMULATED_LCD_LINE1 = "Simulation"
SIMULATED_LCD_LINE2 = "Mode Active"
SIMULATED_BUZZER_ACTIVE = False
SIMULATED_AUDIO_PLAYING = False


def init_simulation():
    """Initialize simulation mode."""
    log("core.simulation", "Actuator simulation mode enabled")
    log("core.simulation", "Fixed values: LEDs={}/{}/{}, Servo={}°, LCD='{}/{}', Buzzer={}, Audio={}".format(
        SIMULATED_LED_GREEN_MODE, SIMULATED_LED_BLUE_MODE, SIMULATED_LED_RED_MODE,
        SIMULATED_SERVO_ANGLE, SIMULATED_LCD_LINE1, SIMULATED_LCD_LINE2,
        SIMULATED_BUZZER_ACTIVE, SIMULATED_AUDIO_PLAYING
    ))
    return True


def update_simulated_actuators():
    """Update state with simulated actuator values.
    
    NOTE: Only sets default values if they haven't been set by a command.
    This allows remote commands to override simulation values.
    """
    # Update LED modes only if not already customized by command
    if state.actuator_state["led_modes"].get("green") == SIMULATED_LED_GREEN_MODE or state.actuator_state["led_modes"].get("green") is None:
        state.actuator_state["led_modes"]["green"] = SIMULATED_LED_GREEN_MODE
    
    if state.actuator_state["led_modes"].get("blue") == SIMULATED_LED_BLUE_MODE or state.actuator_state["led_modes"].get("blue") is None:
        state.actuator_state["led_modes"]["blue"] = SIMULATED_LED_BLUE_MODE
    
    if state.actuator_state["led_modes"].get("red") == SIMULATED_LED_RED_MODE or state.actuator_state["led_modes"].get("red") is None:
        state.actuator_state["led_modes"]["red"] = SIMULATED_LED_RED_MODE
    
    # Update actual LED states based on modes (simplified for simulation)
    state.actuator_state["leds"]["green"] = (state.actuator_state["led_modes"].get("green") in ["on", "blinking"])
    state.actuator_state["leds"]["blue"] = (state.actuator_state["led_modes"].get("blue") in ["on", "blinking"])
    state.actuator_state["leds"]["red"] = (state.actuator_state["led_modes"].get("red") in ["on", "blinking"])
    
    # Update servo only if not already customized by command
    if state.actuator_state["servo"].get("angle") == SIMULATED_SERVO_ANGLE or state.actuator_state["servo"].get("angle") is None:
        state.actuator_state["servo"]["angle"] = SIMULATED_SERVO_ANGLE
    
    state.actuator_state["servo"]["moving"] = False
    
    # Update LCD only if not already customized by command
    if state.actuator_state["lcd"].get("line1") == SIMULATED_LCD_LINE1 or state.actuator_state["lcd"].get("line1") is None:
        state.actuator_state["lcd"]["line1"] = SIMULATED_LCD_LINE1
    
    if state.actuator_state["lcd"].get("line2") == SIMULATED_LCD_LINE2 or state.actuator_state["lcd"].get("line2") is None:
        state.actuator_state["lcd"]["line2"] = SIMULATED_LCD_LINE2
    
    # Update buzzer only if not already customized by command
    if state.actuator_state["buzzer"].get("active") == SIMULATED_BUZZER_ACTIVE or state.actuator_state["buzzer"].get("active") is None:
        state.actuator_state["buzzer"]["active"] = SIMULATED_BUZZER_ACTIVE
    
    # Update audio only if not already customized by command
    if state.actuator_state["audio"].get("playing") == SIMULATED_AUDIO_PLAYING or state.actuator_state["audio"].get("playing") is None:
        state.actuator_state["audio"]["playing"] = SIMULATED_AUDIO_PLAYING
    
    state.actuator_state["audio"]["last_cmd"] = "simulated"
