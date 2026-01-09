"""Actuator system controller for ESP32-B.

Manages all actuator updates in non-blocking fashion using elapsed() timers.
"""

from core.timers import elapsed
from core import state
from debug.debug import log

# Timing constants (milliseconds)
LED_UPDATE_INTERVAL = 50       # Update LED blinking state every 50ms
SERVO_UPDATE_INTERVAL = 100    # Update servo position every 100ms
LCD_UPDATE_INTERVAL = 500      # Update LCD display every 500ms
AUDIO_UPDATE_INTERVAL = 100    # Check audio playback status every 100ms
HEARTBEAT_INTERVAL = 5000      # Log system status every 5 seconds

# Simulation mode flag
_simulation_mode = False

# Import actuator modules at module level (only when not in simulation)
# These will be imported lazily when needed
leds = None
servo = None
lcd = None
buzzer = None
audio = None


def set_simulation_mode(enabled):
    """Enable or disable simulation mode.
    
    Args:
        enabled: True to use simulated actuators, False to use real hardware
    """
    global _simulation_mode
    _simulation_mode = enabled
    log("actuator", "Simulation mode: {}".format("ENABLED" if enabled else "DISABLED"))


def initialize():
    """Initialize all actuators."""
    if _simulation_mode:
        log("actuator", "Skipping hardware initialization (simulation mode)")
        return True
    
    global leds, servo, lcd, buzzer, audio
    
    try:
        # Import actuator modules in hardware mode
        from actuators import leds as leds_module
        from actuators import servo as servo_module
        from actuators import lcd as lcd_module
        from actuators import buzzer as buzzer_module
        from actuators import audio as audio_module
        
        leds = leds_module
        servo = servo_module
        lcd = lcd_module
        buzzer = buzzer_module
        audio = audio_module
        
        log("actuator", "Initializing actuators...")
        leds.init_leds()
        servo.init_servo()
        lcd.init_lcd()
        buzzer.init_buzzer()
        audio.init_audio()
        
        # Configurazione iniziale all'avvio
        log("actuator", "Setting up initial actuator states...")
        
        # Lascia i LED in blinking di default (già impostato in init_leds)
        for led_name in ["green", "blue", "red"]:
            leds.set_led_state(led_name, "blinking")
        
        # Servo già impostato a 0° durante init_servo()
        
        # LCD già con testo di default durante init_lcd()
        
        log("actuator", "All actuators initialized")
        return True
    except Exception as e:
        log("actuator", "Init error: {}".format(e))
        return False


def update():
    """Non-blocking update of all actuators.
    
    Called repeatedly from main loop. Uses elapsed() timers to determine
    when each actuator needs an update without blocking.
    In simulation mode, update simulated values periodically.
    """
    try:
        # In simulation mode, update simulated values periodically
        if _simulation_mode:
            from actuators import simulation
            if elapsed("simulation_update", 1000):  # Update simulation every 1 second
                simulation.update_simulated_actuators()
            return
        
        # Real hardware mode - update actuators
        # Only update if modules are loaded (shouldn't happen if initialize() was called)
        if leds is None:
            return
        
        # Update LED blinking states
        if elapsed("led_update", LED_UPDATE_INTERVAL):
            leds.update_led_test()  # type: ignore
        
        # Update servo position
        if elapsed("servo_update", SERVO_UPDATE_INTERVAL):
            servo.update_servo_test()  # type: ignore
        
        # Update LCD display
        if elapsed("lcd_update", LCD_UPDATE_INTERVAL):
            lcd.update_lcd_test()  # type: ignore
        
        # Update audio playback status
        if elapsed("audio_update", AUDIO_UPDATE_INTERVAL):
            audio.update_audio_test()  # type: ignore
        
        # Periodic heartbeat for system status - DISABLED
        # if elapsed("actuator_heartbeat", HEARTBEAT_INTERVAL):
        #     _log_status()
            
    except Exception as e:
        log("actuator", "Update error: {}".format(e))


def _log_status():
    """Log current actuator system status."""
    led_states = state.actuator_state.get("leds", {})
    led_modes = state.actuator_state.get("led_modes", {})
    buzzer_active = state.actuator_state.get("buzzer", {}).get("active", False)
    audio_playing = state.actuator_state.get("audio", {}).get("playing", False)
    
    status_msg = "LEDs:{} | Servo:{}° | LCD:{} | Buzzer:{} | Audio:{}".format(
        "/".join(["{}:{}".format(k, led_modes.get(k, "?")) for k in led_states.keys()]),
        state.actuator_state.get("servo", {}).get("angle", "N/A"),
        state.actuator_state.get("lcd", {}).get("line1", "OFF")[:8],
        "ON" if buzzer_active else "OFF",
        "ON" if audio_playing else "OFF"
    )
    log("actuator", status_msg)
