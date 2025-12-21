# ===============================
# ESP32_A - CONFIGURATION FILE
# ===============================

# --------- ANALOG SENSORS (ADC1 ONLY) ---------
# Using only ADC1 pins to stay compatible with WiFi / ESP-NOW

# Temperature sensor (DS18B20, digital, OneWire)
TEMP_PIN = 4      # GPIO4 - Digital I/O

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
HEART_RATE_INTERVAL = 1000  # heart rate read interval

# --------- LOGIC THRESHOLDS ---------

# CO alarm threshold (voltage in V)
CO_ALARM_THRESHOLD = 1.6

# Temperature alarm threshold (°C, depends on sensor)
TEMP_ALARM_THRESHOLD = 40.0

# Accelerometer movement threshold (g delta)
ACC_MOVEMENT_THRESHOLD = 1.3

# Heart rate sensor (MAX30100, I2C)
HEART_RATE_SDA_PIN = 21
HEART_RATE_SCL_PIN = 22

# Heart rate thresholds
BPM_LOW_THRESHOLD = 50
BPM_HIGH_THRESHOLD = 120
SPO2_THRESHOLD = 90

# --------- SYSTEM FLAGS (for future expansion) ---------

ENABLE_ESP_NOW = False
ESP32_B_PEER_MAC = b'\xa4\xcf\x12\x9b\x01\x7f'
ACK_TIMEOUT_MS = 200
MAX_RETRIES = 3


# -----------------------------
# SIMULATION SETTINGS
# -----------------------------

SIMULATE_SENSORS = False   # True = genera dati random, False = usa sensori reali
