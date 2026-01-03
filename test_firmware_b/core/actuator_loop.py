"""Actuator system controller for ESP32-B.

Manages all actuator updates in non-blocking fashion using elapsed() timers.
"""

from core.timers import elapsed
from core.state import get_state, update_state
from actuators import leds, servo, lcd, buzzer, audio
from debug.debug import log

# Timing constants (milliseconds)
LED_UPDATE_INTERVAL = 50       # Update LED blinking state every 50ms
SERVO_UPDATE_INTERVAL = 100    # Update servo position every 100ms
LCD_UPDATE_INTERVAL = 500      # Update LCD display every 500ms
AUDIO_UPDATE_INTERVAL = 100    # Check audio playback status every 100ms
HEARTBEAT_INTERVAL = 5000      # Log system status every 5 seconds


def initialize():
    """Initialize all actuators."""
    try:
        log("actuator", "Initializing actuators...")
        leds.init()
        servo.init()
        lcd.init()
        buzzer.init()
        audio.init()
        log("actuator", "All actuators initialized")
        return True
    except Exception as e:
        log("actuator", "Init error: {}".format(e))
        return False


def update():
    """Non-blocking update of all actuators.
    
    Called repeatedly from main loop. Uses elapsed() timers to determine
    when each actuator needs an update without blocking.
    """
    try:
        # Update LED blinking states
        if elapsed("led_update", LED_UPDATE_INTERVAL):
            leds.update()
        
        # Update servo position
        if elapsed("servo_update", SERVO_UPDATE_INTERVAL):
            servo.update()
        
        # Update LCD display
        if elapsed("lcd_update", LCD_UPDATE_INTERVAL):
            lcd.update()
        
        # Update audio playback status
        if elapsed("audio_update", AUDIO_UPDATE_INTERVAL):
            audio.update()
        
        # Periodic heartbeat for system status
        if elapsed("actuator_heartbeat", HEARTBEAT_INTERVAL):
            _log_status()
            
    except Exception as e:
        log("actuator", "Update error: {}".format(e))


def _log_status():
    """Log current actuator system status."""
    state = get_state()
    status_msg = "LEDs: {} | Servo: {} | LCD: {}".format(
        len([1 for k in state.get("leds", {}) if state["leds"][k].get("active")]),
        state.get("servo", {}).get("angle", "N/A"),
        "ON" if state.get("lcd", {}).get("active") else "OFF"
    )
    log("actuator", status_msg)
