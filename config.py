# ===============================
# ESP32_A - CONFIGURATION FILE
# ===============================

# --------- ANALOG SENSORS (ADC1 ONLY) ---------
# Using only ADC1 pins to stay compatible with WiFi / ESP-NOW

# Temperature sensor (analog, 3 wires)
TEMP_PIN = 34      # GPIO34 - ADC1 (input only)

# Carbon Monoxide sensor (DFRobot, analog)
CO_PIN = 35        # GPIO35 - ADC1 (input only)

# Accelerometer (DFRobot, analog X Y Z)
ACC_X_PIN = 32     # GPIO32 - ADC1
ACC_Y_PIN = 33     # GPIO33 - ADC1
ACC_Z_PIN = 36     # GPIO36 - ADC1 (input only)

# --------- DIGITAL INPUTS ---------

# Buttons (DFRobot digital modules)

BUTTON_PINS = {
    "b1": 16,
    "b2": 17,
    "b3": 18
}

# --------- ULTRASONIC SENSOR (HC-SR04) ---------

ULTRASONIC_TRIG_PIN = 26   # OUTPUT
ULTRASONIC_ECHO_PIN = 27   # INPUT (WITH VOLTAGE DIVIDER!)



# --------- TIMING (milliseconds) ---------

TEMP_INTERVAL = 1000      # temperature read interval
CO_INTERVAL = 1000        # CO read interval
ACC_INTERVAL = 100        # accelerometer read interval
BUTTON_INTERVAL = 50      # button scan interval
LOGIC_INTERVAL = 200      # logic evaluation interval
PUBLISH_INTERVAL = 3000   # publish on nodered interval

# --------- LOGIC THRESHOLDS ---------

# CO alarm threshold (raw ADC value, to calibrate)
CO_ALARM_THRESHOLD = 2000

# Temperature alarm threshold (°C, depends on sensor)
TEMP_ALARM_THRESHOLD = 40.0

# Accelerometer movement threshold (raw ADC delta)
ACC_MOVEMENT_THRESHOLD = 500

# --------- SYSTEM FLAGS (for future expansion) ---------

ENABLE_ESP_NOW = False
ENABLE_DEBUG_PRINT = False

# -----------------------------
# SIMULATION SETTINGS
# -----------------------------

SIMULATE_SENSORS = True   # True = genera dati random, False = usa sensori reali