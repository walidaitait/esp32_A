"""Sensor system controller for ESP32-A.

Manages all sensor reads and alarm evaluation in non-blocking fashion.
"""

from core.timers import elapsed
from core import state
from debug.debug import log

# Timing constants (milliseconds)
TEMPERATURE_READ_INTERVAL = 2000  # Read temperature every 2 seconds
CO_READ_INTERVAL = 500            # Read CO sensor every 500ms
ULTRASONIC_READ_INTERVAL = 1000   # Read ultrasonic every 1 second
HEART_RATE_READ_INTERVAL = 1000   # Read heart rate every 1 second
BUTTON_READ_INTERVAL = 50         # Check buttons every 50ms
ACCELEROMETER_READ_INTERVAL = 200 # Read accelerometer every 200ms
ALARM_EVAL_INTERVAL = 500         # Evaluate alarm logic every 500ms
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
        # Import sensor modules in hardware mode
        from sensors import temperature as temp_module
        from sensors import co as co_module
        from sensors import ultrasonic as ultrasonic_module
        from sensors import heart_rate as heart_rate_module
        from sensors import buttons as buttons_module
        from sensors import accelerometer as accelerometer_module
        from logic import alarm_logic as alarm_logic_module
        
        temperature = temp_module
        co = co_module
        ultrasonic = ultrasonic_module
        heart_rate = heart_rate_module
        buttons = buttons_module
        accelerometer = accelerometer_module
        alarm_logic = alarm_logic_module
        
        log("sensor", "Initializing sensors...")
        temperature.init_temperature()
        co.init_co()
        ultrasonic.init_ultrasonic()
        heart_rate.init_heart_rate()
        buttons.init_buttons()
        accelerometer.init_accelerometer()  # Currently not connected on board A; safe no-op if absent
        log("sensor", "All sensors initialized")
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
        # Only read if modules are loaded (shouldn't happen if initialize() was called)
        if temperature is None:
            return
        
        if elapsed("temp_read", TEMPERATURE_READ_INTERVAL, True):
            temperature.read_temperature()
        
        if elapsed("co_read", CO_READ_INTERVAL, True):
            co.read_co()
        
        if elapsed("ultrasonic_read", ULTRASONIC_READ_INTERVAL, True):
            ultrasonic.read_ultrasonic()
        
        if elapsed("heart_rate_read", HEART_RATE_READ_INTERVAL, True):
            heart_rate.read_heart_rate()
        
        if elapsed("button_read", BUTTON_READ_INTERVAL, True):
            buttons.read_buttons()
        
        if elapsed("accelerometer_read", ACCELEROMETER_READ_INTERVAL, True):
            accelerometer.read_accelerometer()  # Will remain idle if the sensor is not wired
        
        # Evaluate alarm logic
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
