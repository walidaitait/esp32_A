"""Sensor system controller for ESP32-A.

Manages all sensor reads and alarm evaluation in non-blocking fashion.
"""

from core.timers import elapsed
from core import state
from sensors import temperature, co, ultrasonic, heart_rate, buttons
from logic import alarm_logic
from debug.debug import log

# Timing constants (milliseconds)
TEMPERATURE_READ_INTERVAL = 2000  # Read temperature every 2 seconds
CO_READ_INTERVAL = 500            # Read CO sensor every 500ms
ULTRASONIC_READ_INTERVAL = 1000   # Read ultrasonic every 1 second
HEART_RATE_READ_INTERVAL = 1000   # Read heart rate every 1 second
BUTTON_READ_INTERVAL = 50         # Check buttons every 50ms
ALARM_EVAL_INTERVAL = 500         # Evaluate alarm logic every 500ms
STATUS_LOG_INTERVAL = 2500        # Log complete status every 2.5 seconds

# Non-blocking state for phase-based reads
_sensor_state = {}


def initialize():
    """Initialize all sensors."""
    try:
        log("sensor", "Initializing sensors...")
        temperature.init_temperature()
        co.init_co()
        ultrasonic.init_ultrasonic()
        heart_rate.init_heart_rate()
        buttons.init_buttons()
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
        # Read sensors based on their individual intervals
        if elapsed("temp_read", TEMPERATURE_READ_INTERVAL):
            temperature.read_temperature()
        
        if elapsed("co_read", CO_READ_INTERVAL):
            co.read_co()
        
        if elapsed("ultrasonic_read", ULTRASONIC_READ_INTERVAL):
            ultrasonic.read_ultrasonic()
        
        if elapsed("heart_rate_read", HEART_RATE_READ_INTERVAL):
            heart_rate.read_heart_rate()
        
        if elapsed("button_read", BUTTON_READ_INTERVAL):
            buttons.read_buttons()
        
        # Evaluate alarm logic
        if elapsed("alarm_eval", ALARM_EVAL_INTERVAL):
            alarm_logic.evaluate_logic()
        
        # Periodic status logging
        if elapsed("sensor_heartbeat", STATUS_LOG_INTERVAL):
            _log_status()
            
    except Exception as e:
        log("sensor", "Update error: {}".format(e))


def _log_status():
    """Log current sensor system status."""
    sensor_data = state.sensor_data
    alarm_level = state.alarm_state.get("level", "UNKNOWN")
    
    status_msg = "T:{} | CO:{} | HR:{} | ALM:{}".format(
        sensor_data.get("temperature", "N/A"),
        sensor_data.get("co", "N/A"),
        sensor_data.get("heart_rate", {}).get("bpm", "N/A"),
        alarm_level
    )
    log("sensor", status_msg)
