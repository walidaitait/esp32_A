"""Actuator system controller for ESP32-B.

Manages all actuator updates in non-blocking fashion using elapsed() timers.
"""

from core.timers import elapsed, user_override_active
from core import state
from debug.debug import log
from time import ticks_ms, ticks_diff, sleep_ms

# Timing constants (milliseconds)
LED_UPDATE_INTERVAL = 50       # Update LED blinking state every 50ms
SERVO_UPDATE_INTERVAL = 100    # Update servo position every 100ms
LCD_UPDATE_INTERVAL = 500      # Update LCD display every 500ms
AUDIO_UPDATE_INTERVAL = 100    # Check audio playback status every 100ms
HEARTBEAT_INTERVAL = 5000      # Log system status every 5 seconds
ESPNOW_TIMEOUT = 10000         # ESP-NOW connection timeout (10 seconds)
ALARM_UPDATE_INTERVAL = 200    # Update alarm indicators every 200ms
EMERGENCY_UPDATE_INTERVAL = 50 # Update emergency logic every 50ms
EMERGENCY_INIT_DELAY = 2000    # Delay before enabling emergency detection (avoid false triggers during boot)

# Simulation mode flag
_simulation_mode = False

# ESP-NOW connection tracking
_last_espnow_message = 0
_espnow_connected = False

# SOS state tracking (to detect state changes)
_last_sos_state = False

# Import actuator modules at module level (only when not in simulation)
# These will be imported lazily when needed
leds = None
servo = None
lcd = None
buzzer = None
audio = None
emergency = None


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
    
    global leds, servo, lcd, buzzer, audio, emergency
    
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
        
        # Always import emergency logic
        from logic import emergency as emergency_module
        emergency = emergency_module
        
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
        
        # IMPORTANT: Reset SOS mode to False at boot (prevent false activation)
        state.actuator_state["sos_mode"] = False
        log("core.actuator", "SOS mode explicitly reset to False")
        
        # LEDs: Green always ON, Blue OFF (will blink only with ESP-NOW), Red OFF
        if config.LEDS_ENABLED and leds:
            leds.set_led_state("green", "on")
            leds.set_led_state("blue", "off")
            leds.set_led_state("red", "off")
        
        # Servo già impostato a 0° durante init_servo()
        
        # LCD: Force clear and default text display
        if config.LCD_ENABLED and lcd:
            lcd.clear()  # type: ignore
            # Wait for clear to complete (blocking during init is OK)
            sleep_ms(5)
            lcd.restore_default()  # type: ignore
            log("core.actuator", "LCD cleared and default text set")
        
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
        
        # === EMERGENCY SOS LOGIC (highest priority) ===
        # Check for emergency SOS activation/deactivation patterns
        # Delay emergency detection for first 2 seconds after boot to avoid false triggers
        if emergency is not None and elapsed("emergency_update", EMERGENCY_UPDATE_INTERVAL) and elapsed("boot_delay", EMERGENCY_INIT_DELAY, False):
            sos_events = emergency.update()  # type: ignore
            
            # Handle single click based on current context
            if sos_events["single_click"]:
                sos_mode = state.actuator_state.get("sos_mode", False)
                
                if sos_mode:
                    # Single click in SOS mode → close SOS call
                    state.actuator_state["sos_mode"] = False
                    log("core.actuator", "=== SOS CALL ENDED (single button click) ===")
                    
                    # Clear SOS display
                    if config.LCD_ENABLED and lcd is not None:
                        lcd.display_custom("", "")  # type: ignore
                else:
                    # Single click outside SOS → mute alarm buzzer (if in warning/danger)
                    alarm_level = state.received_sensor_state.get("alarm_level", "normal")
                    if alarm_level in ("warning", "danger"):
                        state.actuator_state["buzzer"]["alarm_muted"] = True
                        log("core.actuator", ">>> Alarm BUZZER MUTED ({} level) by single button click".format(alarm_level.upper()))
            
            # Handle SOS activation (long press or 5 rapid clicks)
            if sos_events["sos_activated"]:
                state.actuator_state["sos_mode"] = True
                log("core.actuator", "=== SOS CALL ACTIVATED ===")
                
                # Set SOS display
                if config.LCD_ENABLED and lcd is not None:
                    lcd.display_custom("SOS call", "Ringing...")  # type: ignore
                
                # Set red LED to solid (not blinking)
                if config.LEDS_ENABLED and leds is not None:
                    leds.set_led_state("red", "on")  # type: ignore
            
            # Handle SOS deactivation (from emergency module)
            if sos_events["sos_deactivated"]:
                state.actuator_state["sos_mode"] = False
                log("core.actuator", "=== SOS CALL ENDED ===")
                
                # Clear SOS display (will be overwritten by normal logic)
                if config.LCD_ENABLED and lcd is not None:
                    lcd.display_custom("", "")  # type: ignore
        
        # If SOS is active, skip normal actuator updates (emergency takes priority)
        if state.actuator_state.get("sos_mode"):
            # Keep red LED solid in SOS mode
            if config.LEDS_ENABLED and leds is not None:
                if elapsed("led_update", LED_UPDATE_INTERVAL):
                    leds.update_led_test()  # type: ignore (for blinking state machine)
            return
        
        # Check ESP-NOW connection status and update blue LED accordingly
        if config.LEDS_ENABLED and leds is not None and not user_override_active("led_update"):
            espnow_connected = _check_espnow_status()
            if espnow_connected:
                # ESP-NOW connected: Blue LED blinking
                leds.set_led_state("blue", "blinking")
            else:
                # ESP-NOW disconnected: Blue LED OFF
                leds.set_led_state("blue", "off")
        
        # Update LED blinking states
        if config.LEDS_ENABLED and leds is not None:
            if elapsed("led_update", LED_UPDATE_INTERVAL, True):
                leds.update_led_test()  # type: ignore
        
        # Update servo position
        if config.SERVO_ENABLED and servo is not None:
            if elapsed("servo_update", SERVO_UPDATE_INTERVAL, True):
                servo.update_servo_test()  # type: ignore
                servo.update_gate_automation()  # type: ignore
        
        # Update LCD display
        if config.LCD_ENABLED and lcd is not None:
            if elapsed("lcd_update", LCD_UPDATE_INTERVAL, True):
                lcd.update_lcd_test()  # type: ignore
        
        # Update audio playback status
        if config.AUDIO_ENABLED and audio is not None:
            if elapsed("audio_update", AUDIO_UPDATE_INTERVAL, True):
                audio.update_audio_test()  # type: ignore

        # Alarm-driven actuators (LED red, buzzer, LCD alert)
        if elapsed("alarm_update", ALARM_UPDATE_INTERVAL):
            alarm_level = state.received_sensor_state.get("alarm_level", "normal")
            alarm_source = state.received_sensor_state.get("alarm_source")

            # Clear mute when alarm returns to normal
            if alarm_level == "normal":
                state.actuator_state["buzzer"]["alarm_muted"] = False
            if config.LEDS_ENABLED and leds is not None and not user_override_active("led_update"):
                leds.apply_alarm(alarm_level)  # type: ignore
            if config.BUZZER_ENABLED and buzzer is not None and not user_override_active("buzzer_update"):
                # Update buzzer sound playback (phase transitions, tone control)
                buzzer.update()  # type: ignore
                # Set which sound to play based on alarm level
                buzzer.update_alarm_feedback(alarm_level)  # type: ignore
            if config.LCD_ENABLED and lcd is not None and not user_override_active("lcd_update"):
                lcd.update_alarm_display(alarm_level, alarm_source)  # type: ignore
        
        # Check for SOS state change and send immediate event if activated
        _check_sos_state_change()
        
        # Periodic heartbeat for system status - DISABLED
        # if elapsed("actuator_heartbeat", HEARTBEAT_INTERVAL):
        #     _log_status()
            
    except Exception as e:
        log("core.actuator", "Update error: {}".format(e))


def _check_sos_state_change():
    """Detect SOS state changes and send immediate event to Board A."""
    global _last_sos_state
    
    current_sos_state = state.actuator_state.get("sos_mode", False)
    
    # Detect rising edge: SOS just activated (False -> True)
    if current_sos_state and not _last_sos_state:
        log("core.actuator", "SOS state change detected: ACTIVATED")
        # Send immediate event to Board A
        try:
            from communication import espnow_communication
            espnow_communication.send_event_immediate(
                event_type="sos_activated",
                custom_data={"source": "board_b", "timestamp": ticks_ms()}
            )
            log("core.actuator", "SOS event sent to Board A")
        except Exception as e:
            log("core.actuator", "Failed to send SOS event: {}".format(e))
    
    # Detect falling edge: SOS just deactivated (True -> False)
    elif not current_sos_state and _last_sos_state:
        log("core.actuator", "SOS state change detected: DEACTIVATED")
        # Optionally send deactivation event
        try:
            from communication import espnow_communication
            espnow_communication.send_event_immediate(
                event_type="sos_deactivated",
                custom_data={"source": "board_b", "timestamp": ticks_ms()}
            )
            log("core.actuator", "SOS deactivation event sent to Board A")
        except Exception as e:
            log("core.actuator", "Failed to send SOS deactivation event: {}".format(e))
    
    # Update last state
    _last_sos_state = current_sos_state


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
