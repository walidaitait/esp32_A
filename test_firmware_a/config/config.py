"""Configuration for sensor firmware on ESP32-A.

Loads configuration from config.json at startup.
All values below are set from config.json to maintain consistency.
"""

import json

# ===============================
# LOAD CONFIG FROM JSON
# ===============================

_config = {}

def _load_config():
    """Load configuration from config.json"""
    global _config
    try:
        with open('config/config.json', 'r') as f:
            _config = json.load(f)
    except:
        try:
            with open('config.json', 'r') as f:
                _config = json.load(f)
        except:
            print("WARNING: config.json not found, using defaults")
            _config = {}

_load_config()

# ===============================
# FIRMWARE VERSION
# ===============================

FIRMWARE_VERSION = _config.get('firmware_version', 1)

# ===============================
# SIMULATION MODE
# ===============================

SIMULATE_SENSORS = _config.get('simulate_sensors', False)

# ===============================
# SENSOR ENABLED FLAGS
# ===============================

sensors_config = _config.get('sensors', {})
TEMPERATURE_ENABLED = sensors_config.get('temperature', {}).get('enabled', True)
CO_ENABLED = sensors_config.get('co', {}).get('enabled', True)
ULTRASONIC_ENABLED = sensors_config.get('ultrasonic', {}).get('enabled', True)
HEART_RATE_ENABLED = sensors_config.get('heart_rate', {}).get('enabled', True)
ACCELEROMETER_ENABLED = sensors_config.get('accelerometer', {}).get('enabled', False)

# Buttons - individual enable flags
buttons_config = sensors_config.get('buttons', {})
BUTTON_B1_ENABLED = buttons_config.get('b1', {}).get('enabled', True)
BUTTON_B2_ENABLED = buttons_config.get('b2', {}).get('enabled', True)
BUTTON_B3_ENABLED = buttons_config.get('b3', {}).get('enabled', True)
# Overall buttons enabled if at least one button is enabled
BUTTONS_ENABLED = BUTTON_B1_ENABLED or BUTTON_B2_ENABLED or BUTTON_B3_ENABLED

# OTA Button
OTA_BUTTON_ENABLED = _config.get('ota_button_enabled', True)

# ===============================
# PIN ASSIGNMENTS
# ===============================

# Temperature sensor (DS18B20, OneWire)
TEMP_PIN = _config.get('pins', {}).get('temp', 4)

# Carbon Monoxide sensor (DFRobot MQ-7 analog output)
CO_PIN = _config.get('pins', {}).get('co', 35)

# Buttons (DFRobot digital modules)
BUTTON_PINS = _config.get('pins', {}).get('buttons', {
    "b1": 16,
    "b2": 17,
    "b3": 19,
})

# Ultrasonic (HC-SR04)
ULTRASONIC_TRIG_PIN = _config.get('pins', {}).get('ultrasonic_trig', 5)
ULTRASONIC_ECHO_PIN = _config.get('pins', {}).get('ultrasonic_echo', 18)

# Heart rate sensor (MAX30100)
HEART_RATE_SCL_PIN = _config.get('pins', {}).get('heart_rate_scl', 22)
HEART_RATE_SDA_PIN = _config.get('pins', {}).get('heart_rate_sda', 21)


# ===============================
# READ / LOGIC INTERVALS (ms)
# ===============================

intervals = _config.get('intervals_ms', {})
TEMP_INTERVAL = intervals.get('temp', 1000)
CO_INTERVAL = intervals.get('co', 1000)
BUTTON_INTERVAL = intervals.get('button', 50)
HEART_RATE_INTERVAL = intervals.get('heart_rate', 1000)
ULTRASONIC_INTERVAL = intervals.get('ultrasonic', 100)
LOGIC_INTERVAL = intervals.get('logic', 200)


# ===============================
# CO QUICK-BASELINE (used by sensors/co.py)
# ===============================

co_config = _config.get('co_config', {})
CO_BASELINE_MS = co_config.get('baseline_ms', 2000)
CO_MIN_GUARD_MV = co_config.get('min_guard_mv', 5)
CO_PPM_PER_V = co_config.get('ppm_per_v', 400)
CO_PPM_CLAMP = co_config.get('ppm_clamp', 300)
CO_OFFSET_MV = co_config.get('offset_mv', 0)


# ===============================
# INSTANT THRESHOLDS
# ===============================

thresholds = _config.get('thresholds', {})
CO_CRITICAL_PPM = thresholds.get('co_critical_ppm', 50.0)
TEMP_MIN_SAFE = thresholds.get('temp_min_safe', 10.0)
TEMP_MAX_SAFE = thresholds.get('temp_max_safe', 35.0)
BPM_LOW_THRESHOLD = thresholds.get('bpm_low', 50)
BPM_HIGH_THRESHOLD = thresholds.get('bpm_high', 120)
SPO2_THRESHOLD = thresholds.get('spo2', 90)


# ===============================
# ALARM ENABLE FLAGS
# ===============================

alarm_flags = _config.get('alarm_flags', {})
ALARM_CO_ENABLED = alarm_flags.get('co_enabled', True)
ALARM_TEMP_ENABLED = alarm_flags.get('temp_enabled', True)
ALARM_HEART_ENABLED = alarm_flags.get('heart_enabled', True)
ALARM_ULTRASONIC_ENABLED = alarm_flags.get('ultrasonic_enabled', True)


# ===============================
# TEMPORAL WARNING / DANGER WINDOWS (ms)
# ===============================

windows = _config.get('alarm_windows_ms', {})

# CO
CO_WARNING_TIME_MS = windows.get('co_warning', 5000)
CO_DANGER_TIME_MS = windows.get('co_danger', 30000)
CO_RECOVERY_TIME_MS = windows.get('co_recovery', 10000)

# Temperature
TEMP_WARNING_TIME_MS = windows.get('temp_warning', 10000)
TEMP_DANGER_TIME_MS = windows.get('temp_danger', 60000)
TEMP_RECOVERY_TIME_MS = windows.get('temp_recovery', 15000)

# Heart rate / SpO2
HR_WARNING_TIME_MS = windows.get('hr_warning', 10000)
HR_DANGER_TIME_MS = windows.get('hr_danger', 60000)
HR_RECOVERY_TIME_MS = windows.get('hr_recovery', 15000)

# Ultrasonic presence (informational)
ULTRASONIC_PRESENCE_DISTANCE_CM = windows.get('ultrasonic_presence_distance_cm', 50.0)
ULTRASONIC_WARNING_TIME_MS = windows.get('ultrasonic_warning', 2000)
ULTRASONIC_DANGER_TIME_MS = windows.get('ultrasonic_danger', 10000)
ULTRASONIC_RECOVERY_TIME_MS = windows.get('ultrasonic_recovery', 5000)

