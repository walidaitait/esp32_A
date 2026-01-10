"""Actuator system controller for ESP32-B.

Manages all actuator updates in non-blocking fashion using elapsed() timers.
"""

from core.timers import elapsed
from core import state
from debug.debug import log
from time import ticks_ms, ticks_diff

# Timing constants (milliseconds)
LED_UPDATE_INTERVAL = 50       # Update LED blinking state every 50ms
SERVO_UPDATE_INTERVAL = 100    # Update servo position every 100ms
LCD_UPDATE_INTERVAL = 500      # Update LCD display every 500ms
AUDIO_UPDATE_INTERVAL = 100    # Check audio playback status every 100ms
HEARTBEAT_INTERVAL = 5000      # Log system status every 5 seconds
ESPNOW_TIMEOUT = 10000         # ESP-NOW connection timeout (10 seconds)
ALARM_UPDATE_INTERVAL = 200    # Update alarm indicators every 200ms

# Simulation mode flag
_simulation_mode = False

# ESP-NOW connection tracking
_last_espnow_message = 0
_espnow_connected = False

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
    log("core.actuator", "Simulation mode: {}".format("ENABLED" if enabled else "DISABLED"))


def set_espnow_connected(connected):
    """Update ESP-NOW connection status.
    
    Called by ESP-NOW module when receiving messages.
    """
    global _last_espnow_message, _espnow_connected
    _last_espnow_message = ticks_ms()
    _espnow_connected = connected


def _check_espnow_status():
    """Check if ESP-NOW connection is still active (timeout check)."""
    global _espnow_connected
    
    if _last_espnow_message > 0:
        elapsed_time = ticks_diff(ticks_ms(), _last_espnow_message)
        if elapsed_time > ESPNOW_TIMEOUT:
            _espnow_connected = False
        else:
            _espnow_connected = True
    else:
        _espnow_connected = False
    
    return _espnow_connected


def initialize():
    """Initialize all actuators."""
    if _simulation_mode:
        log("core.actuator", "Skipping hardware initialization (simulation mode)")
        return True
    
    global leds, servo, lcd, buzzer, audio
    
    try:
        # Import actuator modules in hardware mode (only enabled actuators)
        from config import config
        
        if config.LEDS_ENABLED:
            from actuators import leds as leds_module
            leds = leds_module
        
        if config.SERVO_ENABLED:
            from actuators import servo as servo_module
            servo = servo_module
        
        if config.LCD_ENABLED:
            from actuators import lcd as lcd_module
            lcd = lcd_module
        
        if config.BUZZER_ENABLED:
            from actuators import buzzer as buzzer_module
            buzzer = buzzer_module
        
        if config.AUDIO_ENABLED:
            from actuators import audio as audio_module
            audio = audio_module
        
        log("core.actuator", "Initializing enabled actuators...")
        
        if config.LEDS_ENABLED and leds:
            leds.init_leds()
            log("core.actuator", "LEDs initialized")
        
        if config.SERVO_ENABLED and servo:
            servo.init_servo()
            log("core.actuator", "Servo initialized")
        
        if config.LCD_ENABLED and lcd:
            lcd.init_lcd()
            log("core.actuator", "LCD initialized")
        
        if config.BUZZER_ENABLED and buzzer:
            buzzer.init_buzzer()
            log("core.actuator", "Buzzer initialized")
        
        if config.AUDIO_ENABLED and audio:
            audio.init_audio()
            log("core.actuator", "Audio initialized")
        
        # Configurazione iniziale all'avvio (solo per componenti abilitati)
        log("core.actuator", "Setting up initial actuator states...")
        
        # LEDs: Green always ON, Blue OFF (will blink only with ESP-NOW), Red OFF
        if config.LEDS_ENABLED and leds:
            leds.set_led_state("green", "on")
            leds.set_led_state("blue", "off")
            leds.set_led_state("red", "off")
        
        # Servo già impostato a 0° durante init_servo()
        # LCD già con testo di default durante init_lcd()
        
        log("core.actuator", "Enabled actuators initialized successfully")
        return True
    except Exception as e:
        log("core.actuator", "Init error: {}".format(e))
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
        
        # Real hardware mode - update actuators (only enabled ones)
        from config import config
        
        # Check ESP-NOW connection status and update blue LED accordingly
        if config.LEDS_ENABLED and leds is not None:
            espnow_connected = _check_espnow_status()
            if espnow_connected:
                # ESP-NOW connected: Blue LED blinking
                leds.set_led_state("blue", "blinking")
            else:
                # ESP-NOW disconnected: Blue LED OFF
                leds.set_led_state("blue", "off")
        
        # Update LED blinking states
        if config.LEDS_ENABLED and leds is not None:
            if elapsed("led_update", LED_UPDATE_INTERVAL):
                leds.update_led_test()  # type: ignore
        
        # Update servo position
        if config.SERVO_ENABLED and servo is not None:
            if elapsed("servo_update", SERVO_UPDATE_INTERVAL):
                servo.update_servo_test()  # type: ignore
                servo.update_gate_automation()  # type: ignore
        
        # Update LCD display
        if config.LCD_ENABLED and lcd is not None:
            if elapsed("lcd_update", LCD_UPDATE_INTERVAL):
                lcd.update_lcd_test()  # type: ignore
        
        # Update audio playback status
        if config.AUDIO_ENABLED and audio is not None:
            if elapsed("audio_update", AUDIO_UPDATE_INTERVAL):
                audio.update_audio_test()  # type: ignore

        # Alarm-driven actuators (LED red, buzzer, LCD alert)
        if elapsed("alarm_update", ALARM_UPDATE_INTERVAL):
            alarm_level = state.received_sensor_state.get("alarm_level", "normal")
            alarm_source = state.received_sensor_state.get("alarm_source")
            if config.LEDS_ENABLED and leds is not None:
                leds.apply_alarm(alarm_level)  # type: ignore
            if config.BUZZER_ENABLED and buzzer is not None:
                buzzer.update_alarm_feedback(alarm_level)  # type: ignore
            if config.LCD_ENABLED and lcd is not None:
                lcd.update_alarm_display(alarm_level, alarm_source)  # type: ignore
        
        # Periodic heartbeat for system status - DISABLED
        # if elapsed("actuator_heartbeat", HEARTBEAT_INTERVAL):
        #     _log_status()
            
    except Exception as e:
        log("core.actuator", "Update error: {}".format(e))


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
    log("core.actuator", status_msg)
