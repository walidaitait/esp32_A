"""Configuration for sensor firmware on ESP32-A.

Defines pins, read intervals, thresholds, and timing parameters for
warning/danger logic.
"""

# ===============================
# PIN ASSIGNMENTS
# ===============================

# Temperature sensor (DS18B20, OneWire)
TEMP_PIN = 4      # GPIO4

# Carbon Monoxide sensor (DFRobot MQ-7 analog output)
CO_PIN = 35       # GPIO35 (ADC1 input only)

# Buttons (DFRobot digital modules)
BUTTON_PINS = {
    "b1": 16,
    "b2": 17,
    "b3": 19,
}

# Ultrasonic (HC-SR04)
ULTRASONIC_TRIG_PIN = 5    # GPIO5 (output)
ULTRASONIC_ECHO_PIN = 18   # GPIO18 (input, with voltage divider)

# Heart rate sensor (MAX30100)
HEART_RATE_SCL_PIN = 22
HEART_RATE_SDA_PIN = 21


# ===============================
# READ / LOGIC INTERVALS (ms)
# ===============================

TEMP_INTERVAL = 1000        # Temperature read interval
CO_INTERVAL = 1000          # CO read interval
BUTTON_INTERVAL = 50        # Button scan interval
HEART_RATE_INTERVAL = 1000  # Heart rate read interval
ULTRASONIC_INTERVAL = 100   # Ultrasonic read interval

LOGIC_INTERVAL = 200        # Alarm-logic evaluation interval


# ===============================
# CO QUICK-BASELINE (used by sensors/co.py)
# ===============================

CO_BASELINE_MS = 4000       # Baseline window at startup
CO_MIN_GUARD_MV = 20        # Ignore deltas below this noise floor (mV)
CO_PPM_PER_V = 400          # PPM per volt over baseline
CO_PPM_CLAMP = 500          # Max reported PPM
CO_OFFSET_MV = 0            # Optional offset after baseline (mV)


# ===============================
# INSTANT THRESHOLDS
# ===============================

CO_CRITICAL_PPM = 50.0      # Critical CO threshold

TEMP_MIN_SAFE = 10.0        # Minimum safe house temperature (°C)
TEMP_MAX_SAFE = 35.0        # Maximum safe house temperature (°C)

BPM_LOW_THRESHOLD = 50      # Heart rate low threshold
BPM_HIGH_THRESHOLD = 120    # Heart rate high threshold
SPO2_THRESHOLD = 90         # SpO2 minimum threshold


# ===============================
# ALARM ENABLE FLAGS
# ===============================

ALARM_CO_ENABLED = True
ALARM_TEMP_ENABLED = True
ALARM_HEART_ENABLED = True
ALARM_ULTRASONIC_ENABLED = True


# ===============================
# TEMPORAL WARNING / DANGER WINDOWS (ms)
# ===============================

# CO
CO_WARNING_TIME_MS = 5000        # Critical CO for at least 5s -> warning
CO_DANGER_TIME_MS = 30000        # Critical CO for at least 30s -> danger
CO_RECOVERY_TIME_MS = 10000      # Normal CO for 10s -> back to normal

# Temperature
TEMP_WARNING_TIME_MS = 10000     # Out of range for 10s -> warning
TEMP_DANGER_TIME_MS = 60000      # Out of range for 60s -> danger
TEMP_RECOVERY_TIME_MS = 15000    # In range for 15s -> normal

# Heart rate / SpO2
HR_WARNING_TIME_MS = 10000       # Abnormal for 10s -> warning
HR_DANGER_TIME_MS = 60000        # Abnormal for 60s -> danger
HR_RECOVERY_TIME_MS = 15000      # Normal for 15s -> normal

# Ultrasonic presence (informational)
ULTRASONIC_PRESENCE_DISTANCE_CM = 50.0  # Presence if closer than this
ULTRASONIC_WARNING_TIME_MS = 2000       # Presence for 2s -> warning (unused in alarm)
ULTRASONIC_DANGER_TIME_MS = 10000       # Presence for 10s -> danger (unused in alarm)
ULTRASONIC_RECOVERY_TIME_MS = 5000      # Absence for 5s -> normal
