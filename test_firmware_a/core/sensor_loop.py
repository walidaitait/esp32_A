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
    log("sensor", "Simulation mode: {}".format("ENABLED" if enabled else "DISABLED"))


def initialize():
    """Initialize all sensors."""
    if _simulation_mode:
        log("sensor", "Skipping hardware initialization (simulation mode)")
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
        
        log("sensor", "Initializing enabled sensors...")
        
        if config.TEMPERATURE_ENABLED and temperature:
            if temperature.init_temperature():
                log("sensor", "Temperature sensor initialized")
            else:
                log("sensor", "Temperature sensor init failed - disabling")
                temperature = None

        if config.CO_ENABLED and co:
            if co.init_co():
                log("sensor", "CO sensor initialized")
            else:
                log("sensor", "CO sensor init failed - disabling")
                co = None

        if config.ULTRASONIC_ENABLED and ultrasonic:
            if ultrasonic.init_ultrasonic():
                log("sensor", "Ultrasonic sensor initialized")
            else:
                log("sensor", "Ultrasonic sensor init failed - disabling")
                ultrasonic = None

        if config.HEART_RATE_ENABLED and heart_rate:
            if heart_rate.init_heart_rate():
                log("sensor", "Heart rate sensor initialized")
            else:
                log("sensor", "Heart rate init failed - disabling")
                heart_rate = None

        if config.BUTTONS_ENABLED and buttons:
            if buttons.init_buttons():
                log("sensor", "Buttons initialized")
            else:
                log("sensor", "Buttons init failed - disabling")
                buttons = None

        if config.ACCELEROMETER_ENABLED and accelerometer:
            if accelerometer.init_accelerometer():
                log("sensor", "Accelerometer initialized")
            else:
                log("sensor", "Accelerometer init failed - disabling")
                accelerometer = None
        
        log("sensor", "Enabled sensors initialized successfully")
        return True
    except Exception as e:
        log("sensor", "Init error: {}".format(e))
        return False


def update():
    """Non-blocking update of all sensors and alarm logic.
    
    Called repeatedly from main loop. Each sensor uses elapsed() timers
    to determine when to read without blocking the main loop.
    """
    try:
        # In simulation mode, update simulated values periodically
        if _simulation_mode:
            from sensors import simulation
            if elapsed("simulation_update", 1000):  # Update simulation every 1 second
                simulation.update_simulated_sensors()
            return
        
        # Real hardware mode - read sensors based on their individual intervals
        # Only read if modules are loaded AND enabled
        from config import config
        
        if config.TEMPERATURE_ENABLED and temperature is not None:
            if elapsed("temp_read", TEMPERATURE_READ_INTERVAL, True):
                temperature.read_temperature()
        
        if config.CO_ENABLED and co is not None:
            if elapsed("co_read", CO_READ_INTERVAL, True):
                co.read_co()
        
        if config.ULTRASONIC_ENABLED and ultrasonic is not None:
            if elapsed("ultrasonic_read", ULTRASONIC_READ_INTERVAL, True):
                ultrasonic.read_ultrasonic()
        
        if config.HEART_RATE_ENABLED and heart_rate is not None:
            if elapsed("heart_rate_read", HEART_RATE_READ_INTERVAL, True):
                heart_rate.read_heart_rate()
        
        if config.BUTTONS_ENABLED and buttons is not None:
            if elapsed("button_read", BUTTON_READ_INTERVAL, True):
                buttons.read_buttons()
        
        if config.ACCELEROMETER_ENABLED and accelerometer is not None:
            if elapsed("accelerometer_read", ACCELEROMETER_READ_INTERVAL, True):
                accelerometer.read_accelerometer()
        
        # Evaluate alarm logic (always run if available)
        if alarm_logic is not None:
            if elapsed("alarm_eval", ALARM_EVAL_INTERVAL):
                alarm_logic.evaluate_logic()
        
        # Periodic status logging - DISABLED
        # if elapsed("sensor_heartbeat", STATUS_LOG_INTERVAL):
        #     _log_status()
            
    except Exception as e:
        log("sensor", "Update error: {}".format(e))


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
    log("sensor", status_msg)
