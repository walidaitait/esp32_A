"""Sensor system controller for ESP32-A.

Manages all sensor reads and alarm evaluation in non-blocking fashion.
"""

from core.timers import elapsed
from core.state import get_state, update_state
from sensors.temperature import read as read_temperature
from sensors.co import read as read_co
from sensors.ultrasonic import read as read_ultrasonic
from sensors.heart_rate import read as read_heart_rate
from sensors.buttons import read as read_buttons
from logic.alarm_logic import evaluate as evaluate_alarm
from debug.debug import log
from debug.remote_log import broadcast

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
        read_temperature()  # Start temperature conversion (phase 1)
        read_co()
        read_ultrasonic()
        read_heart_rate()
        read_buttons()
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
            read_temperature()
        
        if elapsed("co_read", CO_READ_INTERVAL):
            read_co()
        
        if elapsed("ultrasonic_read", ULTRASONIC_READ_INTERVAL):
            read_ultrasonic()
        
        if elapsed("heart_rate_read", HEART_RATE_READ_INTERVAL):
            read_heart_rate()
        
        if elapsed("button_read", BUTTON_READ_INTERVAL):
            read_buttons()
        
        # Evaluate alarm logic
        if elapsed("alarm_eval", ALARM_EVAL_INTERVAL):
            evaluate_alarm()
        
        # Periodic status logging
        if elapsed("sensor_heartbeat", STATUS_LOG_INTERVAL):
            _log_status()
            
    except Exception as e:
        log("sensor", "Update error: {}".format(e))


def _log_status():
    """Log current sensor system status."""
    state = get_state()
    sensor_data = state.get("sensors", {})
    alarm_level = state.get("alarm", {}).get("level", "UNKNOWN")
    
    status_msg = "T:{} | CO:{} | HR:{} | ALM:{}".format(
        sensor_data.get("temperature", "N/A"),
        sensor_data.get("co_level", "N/A"),
        sensor_data.get("heart_rate", "N/A"),
        alarm_level
    )
    log("sensor", status_msg)
    broadcast(status_msg)
