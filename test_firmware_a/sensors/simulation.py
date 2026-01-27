"""Sensor simulation module for hardware-less testing.

Imported by: core.sensor_loop, main.py
Imports: core.state, debug.debug

Provides realistic simulated sensor values without requiring physical hardware.
Used when config.SIMULATE_SENSORS is True in main.py.

Features:
- Fixed default values that mimic safe/normal sensor readings
- Values can be overridden at runtime via UDP commands (simulate command)
- Alarm logic still runs normally using simulated values
- Useful for:
  * Development without hardware
  * Testing alarm logic thresholds
  * Demo/presentation mode
  * CI/CD automated testing

Simulated sensors:
- Temperature: 23.5°C (room temperature)
- CO: 10 PPM (safe level, well below 50 PPM threshold)
- Heart rate: 75 BPM (normal resting)
- SpO2: 98% (healthy oxygen saturation)
- Ultrasonic: 45cm (within presence detection range)
- Buttons: B1=off, B2=on, B3=off

Note: Simulated values are initialized ONCE. Remote commands can
override them dynamically. Alarm logic is NOT mocked - it evaluates
real alarm conditions based on the simulated sensor values.
"""

from core import state
from debug.debug import log

# Fixed simulated values (can be made dynamic in the future)
SIMULATED_TEMPERATURE = 23.5
SIMULATED_CO = 10  # Safe value (< 50 PPM threshold)
SIMULATED_HEART_RATE_BPM = 75
SIMULATED_HEART_RATE_SPO2 = 98
SIMULATED_ULTRASONIC_DISTANCE = 45
SIMULATED_ULTRASONIC_PRESENCE = True
SIMULATED_BUTTON_B1 = False
SIMULATED_BUTTON_B2 = True
SIMULATED_BUTTON_B3 = False


def init_simulation():
    """Initialize simulation mode."""
    log("core.simulation", "Sensor simulation mode enabled")
    log("core.simulation", "Fixed values: T={}, CO={}, HR={}, SpO2={}, Dist={}cm".format(
        SIMULATED_TEMPERATURE, SIMULATED_CO, SIMULATED_HEART_RATE_BPM,
        SIMULATED_HEART_RATE_SPO2, SIMULATED_ULTRASONIC_DISTANCE
    ))
    return True


def update_simulated_sensors():
    """Initialize simulated sensor values with defaults.
    
    Sets default values ONLY if sensors are None (first initialization).
    Allows remote commands to override values at runtime.
    Alarm logic is NOT simulated - it runs on actual sensor values.
    """
    # Initialize sensor data with defaults if not yet set
    if state.sensor_data.get("temperature") is None:
        state.sensor_data["temperature"] = SIMULATED_TEMPERATURE
    
    if state.sensor_data.get("co") is None:
        state.sensor_data["co"] = SIMULATED_CO
    
    if state.sensor_data.get("ultrasonic_distance_cm") is None:
        state.sensor_data["ultrasonic_distance_cm"] = SIMULATED_ULTRASONIC_DISTANCE
    
    # Heart rate - initialize only if None
    if state.sensor_data.get("heart_rate") is None:
        state.sensor_data["heart_rate"] = {
            "ir": 10000,  # Simulated IR value
            "red": 9500,  # Simulated RED value
            "bpm": SIMULATED_HEART_RATE_BPM,
            "spo2": SIMULATED_HEART_RATE_SPO2,
            "status": "simulated"
        }
    
    if state.sensor_data.get("ultrasonic_presence") is None:
        state.sensor_data["ultrasonic_presence"] = SIMULATED_ULTRASONIC_PRESENCE
    
    # Initialize button states if not set
    if state.button_state.get("b1") is None:
        state.button_state["b1"] = SIMULATED_BUTTON_B1
    if state.button_state.get("b2") is None:
        state.button_state["b2"] = SIMULATED_BUTTON_B2
    if state.button_state.get("b3") is None:
        state.button_state["b3"] = SIMULATED_BUTTON_B3
    
    # NOTE: Alarm levels are NOT reset here.
    # They are computed by alarm_logic.evaluate_logic() based on actual sensor values.
