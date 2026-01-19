"""Sensor system controller for ESP32-A.

Manages all sensor reads and alarm evaluation in non-blocking fashion.
"""

from core.timers import elapsed
from core import state
from debug.debug import log

# Timing constants (milliseconds) - use values from config where available
from config import config as _cfg
TEMPERATURE_READ_INTERVAL = _cfg.TEMP_INTERVAL
CO_READ_INTERVAL = _cfg.CO_INTERVAL
ULTRASONIC_READ_INTERVAL = _cfg.ULTRASONIC_INTERVAL
HEART_RATE_READ_INTERVAL = _cfg.HEART_RATE_INTERVAL
BUTTON_READ_INTERVAL = _cfg.BUTTON_INTERVAL
ACCELEROMETER_READ_INTERVAL = 200 # Read accelerometer every 200ms
ALARM_EVAL_INTERVAL = _cfg.LOGIC_INTERVAL
STATUS_LOG_INTERVAL = 2500        # Log complete status every 2.5 seconds

# Simulation mode flag
_simulation_mode = False

# Alarm state tracking (to detect critical state changes)
_last_alarm_level = "normal"

# SOS state tracking from Board B (to detect SOS activation)
_last_sos_state_from_b = False

# Import sensor modules conditionally (only when not in simulation)
# These will be imported lazily when needed
temperature = None
co = None
ultrasonic = None
heart_rate = None
buttons = None
accelerometer = None
alarm_logic = None


def set_simulation_mode(enabled):
    """Enable or disable simulation mode.
    
    Args:
        enabled: True to use simulated sensors, False to use real hardware
    """
    global _simulation_mode
    _simulation_mode = enabled
    log("core.sensor", "Simulation mode: {}".format("ENABLED" if enabled else "DISABLED"))


def initialize():
    """Initialize all sensors."""
    if _simulation_mode:
        log("core.sensor", "Skipping hardware initialization (simulation mode)")
        return True
    
    global temperature, co, ultrasonic, heart_rate, buttons, accelerometer, alarm_logic
    
    try:
        # Import sensor modules in hardware mode (only enabled sensors)
        from config import config
        
        if config.TEMPERATURE_ENABLED:
            from sensors import temperature as temp_module
            temperature = temp_module
        
        if config.CO_ENABLED:
            from sensors import co as co_module
            co = co_module
        
        if config.ULTRASONIC_ENABLED:
            from sensors import ultrasonic as ultrasonic_module
            ultrasonic = ultrasonic_module
        
        if config.HEART_RATE_ENABLED:
            from sensors import heart_rate as heart_rate_module
            heart_rate = heart_rate_module
        
        if config.BUTTONS_ENABLED:
            from sensors import buttons as buttons_module
            buttons = buttons_module
        
        if config.ACCELEROMETER_ENABLED:
            from sensors import accelerometer as accelerometer_module
            accelerometer = accelerometer_module
        
        # Always import alarm logic
        from logic import alarm_logic as alarm_logic_module
        alarm_logic = alarm_logic_module
        
        log("core.sensor", "Initializing enabled sensors...")
        
        if config.TEMPERATURE_ENABLED and temperature:
            if temperature.init_temperature():
                log("core.sensor", "Temperature sensor initialized")
            else:
                log("core.sensor", "Temperature sensor init failed - disabling")
                temperature = None

        if config.CO_ENABLED and co:
            if co.init_co():
                log("core.sensor", "CO sensor initialized")
            else:
                log("core.sensor", "CO sensor init failed - disabling")
                co = None

        if config.ULTRASONIC_ENABLED and ultrasonic:
            if ultrasonic.init_ultrasonic():
                log("core.sensor", "Ultrasonic sensor initialized")
            else:
                log("core.sensor", "Ultrasonic sensor init failed - disabling")
                ultrasonic = None

        if config.HEART_RATE_ENABLED and heart_rate:
            if heart_rate.init_heart_rate():
                log("core.sensor", "Heart rate sensor initialized")
            else:
                log("core.sensor", "Heart rate init failed - disabling")
                heart_rate = None

        if config.BUTTONS_ENABLED and buttons:
            if buttons.init_buttons():
                log("core.sensor", "Buttons initialized")
            else:
                log("core.sensor", "Buttons init failed - disabling")
                buttons = None

        if config.ACCELEROMETER_ENABLED and accelerometer:
            if accelerometer.init_accelerometer():
                log("core.sensor", "Accelerometer initialized")
            else:
                log("core.sensor", "Accelerometer init failed - disabling")
                accelerometer = None
        
        log("core.sensor", "Enabled sensors initialized successfully")
        return True
    except Exception as e:
        log("core.sensor", "Init error: {}".format(e))
        return False


def update():
    """Non-blocking update of all sensors and alarm logic.
    
    Called repeatedly from main loop. Each sensor uses elapsed() timers
    to determine when to read without blocking the main loop.
    """
    try:
        # In simulation mode, initialize simulated values and run alarm logic
        if _simulation_mode:
            from sensors import simulation
            # Initialize simulated sensors once (first call)
            if elapsed("simulation_init", 1000):
                simulation.update_simulated_sensors()
            # Still evaluate alarm logic based on current sensor values
            if alarm_logic is not None:
                if elapsed("alarm_eval", ALARM_EVAL_INTERVAL):
                    try:
                        alarm_logic.evaluate_logic()
                    except Exception as e:
                        log("core.sensor", "update(alarm_logic) error: {}".format(e))
            return
        
        # Real hardware mode - read sensors based on their individual intervals
        # Only read if modules are loaded AND enabled
        from config import config
        
        if config.TEMPERATURE_ENABLED and temperature is not None:
            if elapsed("temp_read", TEMPERATURE_READ_INTERVAL, True):
                try:
                    temperature.read_temperature()
                except Exception as e:
                    log("core.sensor", "update(temp) error: {}".format(e))
        
        if config.CO_ENABLED and co is not None:
            if elapsed("co_read", CO_READ_INTERVAL, True):
                try:
                    co.read_co()
                except Exception as e:
                    log("core.sensor", "update(co) error: {}".format(e))
        
        if config.ULTRASONIC_ENABLED and ultrasonic is not None:
            if elapsed("ultrasonic_read", ULTRASONIC_READ_INTERVAL, True):
                try:
                    ultrasonic.read_ultrasonic()
                except Exception as e:
                    log("core.sensor", "update(ultrasonic) error: {}".format(e))
        
        if config.HEART_RATE_ENABLED and heart_rate is not None:
            if elapsed("heart_rate_read", HEART_RATE_READ_INTERVAL, True):
                try:
                    heart_rate.read_heart_rate()
                except Exception as e:
                    log("core.sensor", "update(heart_rate) error: {}".format(e))
        
        if config.BUTTONS_ENABLED and buttons is not None:
            if elapsed("button_read", BUTTON_READ_INTERVAL, True):
                try:
                    buttons.read_buttons()
                except Exception as e:
                    log("core.sensor", "update(buttons) error: {}".format(e))
        
        if config.ACCELEROMETER_ENABLED and accelerometer is not None:
            if elapsed("accelerometer_read", ACCELEROMETER_READ_INTERVAL, True):
                try:
                    accelerometer.read_accelerometer()
                except Exception as e:
                    log("core.sensor", "update(accelerometer) error: {}".format(e))
        
        # Evaluate alarm logic (always run if available)
        if alarm_logic is not None:
            if elapsed("alarm_eval", ALARM_EVAL_INTERVAL):
                try:
                    alarm_logic.evaluate_logic()
                    # Check for critical alarm state changes
                    _check_alarm_state_change()
                    # Check for SOS activation from Board B
                    _check_sos_from_b()
                except Exception as e:
                    log("core.sensor", "update(alarm_logic) error: {}".format(e))
        
        # Periodic status logging - DISABLED
        # if elapsed("sensor_heartbeat", STATUS_LOG_INTERVAL):
        #     _log_status()
            
    except Exception as e:
        log("core.sensor", "Update error: {}".format(e))


def _check_alarm_state_change():
    """Detect critical alarm state changes and send immediate event to Board B."""
    global _last_alarm_level
    from time import ticks_ms
    
    current_alarm_level = state.alarm_state.get("level", "normal")
    alarm_source = state.alarm_state.get("source")
    
    # Detect transition to critical alarm (normal/warning -> critical)
    if current_alarm_level == "critical" and _last_alarm_level != "critical":
        log("core.sensor", "CRITICAL alarm state change detected")
        # Send immediate event to Board B
        try:
            from communication import espnow_communication
            espnow_communication.send_event_immediate(
                event_type="alarm_critical",
                custom_data={
                    "source": alarm_source,
                    "previous_level": _last_alarm_level,
                    "timestamp": ticks_ms()
                }
            )
            log("core.sensor", "Critical alarm event sent to Board B")
        except Exception as e:
            log("core.sensor", "Failed to send alarm event: {}".format(e))
    
    # Detect transition from critical to lower level (critical -> warning/normal)
    elif _last_alarm_level == "critical" and current_alarm_level != "critical":
        log("core.sensor", "Alarm de-escalation detected: critical -> {}".format(current_alarm_level))
        # Optionally send de-escalation event
        try:
            from communication import espnow_communication
            espnow_communication.send_event_immediate(
                event_type="alarm_cleared",
                custom_data={
                    "new_level": current_alarm_level,
                    "timestamp": ticks_ms()
                }
            )
            log("core.sensor", "Alarm cleared event sent to Board B")
        except Exception as e:
            log("core.sensor", "Failed to send alarm cleared event: {}".format(e))
    
    # Update last state
    _last_alarm_level = current_alarm_level


def _check_sos_from_b():
    """Check for SOS activation from Board B and handle it.
    
    This function detects when Board B activates SOS mode (button press)
    and executes the appropriate response on Board A (control center).
    
    TODO: Implement SOS response logic when requirements are defined.
    Possible actions:
    - Send notification/alert to external system
    - Trigger emergency protocol
    - Log SOS event with timestamp
    - Activate additional sensors or actuators
    - Send confirmation back to B
    """
    global _last_sos_state_from_b
    from time import ticks_ms
    
    # Get current SOS state from Board B (received via ESP-NOW)
    current_sos_from_b = state.received_actuator_state.get("sos_mode", False)
    
    # Detect rising edge: SOS just activated on B (False -> True)
    if current_sos_from_b and not _last_sos_state_from_b:
        log("core.sensor", ">>> SOS ACTIVATED from Board B <<<")
        
        # TODO: Call future SOS handling logic here
        # Example placeholder:
        # handle_sos_emergency_protocol()
        # send_sos_notification_to_external_system()
        # activate_emergency_sensors()
        
        log("core.sensor", "SOS handling placeholder - implement response logic here")
    
    # Detect falling edge: SOS deactivated on B (True -> False)
    elif not current_sos_from_b and _last_sos_state_from_b:
        log("core.sensor", ">>> SOS DEACTIVATED from Board B <<<")
        
        # TODO: Call future SOS deactivation logic here
        # Example placeholder:
        # deactivate_sos_emergency_protocol()
        
        log("core.sensor", "SOS deactivation - implement cleanup logic here")
    
    # Update last state
    _last_sos_state_from_b = current_sos_from_b


def _log_status():
    """Log current sensor system status."""
    sensor_data = state.sensor_data
    alarm_level = state.alarm_state.get("level", "UNKNOWN")
    
    status_msg = "T:{} | CO:{} | HR:{} | US:{} | BTN:{} | ACC:{} | ALM:{}".format(
        sensor_data.get("temperature", "N/A"),
        sensor_data.get("co", "N/A"),
        sensor_data.get("heart_rate", {}).get("bpm", "N/A"),
        sensor_data.get("ultrasonic_distance_cm", "N/A"),
        state.button_state,
        sensor_data.get("acc", "N/A"),
        alarm_level
    )
    log("core.sensor", status_msg)
