"""Sensor simulation module for testing.

Provides simulated sensor values without requiring actual hardware.
Used when SIMULATE_SENSORS is True in main.py.
"""

from core import state
from debug.debug import log

# Fixed simulated values (can be made dynamic in the future)
SIMULATED_TEMPERATURE = 23.5
SIMULATED_CO = 150
SIMULATED_HEART_RATE_BPM = 75
SIMULATED_HEART_RATE_SPO2 = 98
SIMULATED_ULTRASONIC_DISTANCE = 45
SIMULATED_ULTRASONIC_PRESENCE = True
SIMULATED_BUTTON_B1 = False
SIMULATED_BUTTON_B2 = True
SIMULATED_BUTTON_B3 = False


def init_simulation():
    """Initialize simulation mode."""
    log("simulation", "Sensor simulation mode enabled")
    log("simulation", "Fixed values: T={}, CO={}, HR={}, SpO2={}, Dist={}cm".format(
        SIMULATED_TEMPERATURE, SIMULATED_CO, SIMULATED_HEART_RATE_BPM,
        SIMULATED_HEART_RATE_SPO2, SIMULATED_ULTRASONIC_DISTANCE
    ))
    return True


def update_simulated_sensors():
    """Update state with simulated sensor values."""
    # Update sensor data
    state.sensor_data["temperature"] = SIMULATED_TEMPERATURE
    state.sensor_data["co"] = SIMULATED_CO
    state.sensor_data["heart_rate"] = {
        "ir": 10000,  # Simulated IR value
        "red": 9500,  # Simulated RED value
        "bpm": SIMULATED_HEART_RATE_BPM,
        "spo2": SIMULATED_HEART_RATE_SPO2,
        "status": "simulated"
    }
    state.sensor_data["ultrasonic_distance_cm"] = SIMULATED_ULTRASONIC_DISTANCE
    state.sensor_data["ultrasonic_presence"] = SIMULATED_ULTRASONIC_PRESENCE
    
    # Update button states
    state.button_state["b1"] = SIMULATED_BUTTON_B1
    state.button_state["b2"] = SIMULATED_BUTTON_B2
    state.button_state["b3"] = SIMULATED_BUTTON_B3
    
    # Update system state (simulated alarm levels)
    state.system_state["co_level"] = "normal"
    state.system_state["temp_level"] = "normal"
    state.system_state["heart_level"] = "normal"
    
    state.alarm_state["level"] = "normal"
    state.alarm_state["source"] = None
