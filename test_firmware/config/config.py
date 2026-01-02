"""Configuration for sensor firmware on ESP32-A.

Here we define pins, read intervals and all alarm logic
thresholds/timings (normal/warning/danger).
"""

# ===============================
# INTER-DEVICE COMMUNICATION
# ===============================

# Auto-discovery via UDP beacon - plug and play!
# No hardcoded MAC or IP needed

# Communication update frequency (ms)
COMM_UPDATE_INTERVAL_MS = 100

# ESPNOW peer-to-peer transport (bypasses WiFi client isolation). Comandi A->B su ESP-NOW; WiFi resta per log/OTA.
USE_ESPNOW = True

# MAC addresses (bytes) of the devices
MAC_A_BYTES = b"\x5c\x01\x3b\x5c\x2c\x34"
MAC_B_BYTES = b"\x5c\x01\x3b\x87\x53\x10"

# ===============================
# SENSOR PINS
# ===============================

# Temperature sensor (DS18B20, digital, OneWire)
TEMP_PIN = 4      # GPIO4 - Digital I/O

# Carbon Monoxide sensor (DFRobot, analog)
CO_PIN = 35       # GPIO35 - ADC1 (input only)

# Accelerometer (DFRobot, analog X Y Z)
ACC_X_PIN = 32    # GPIO32 - ADC1
ACC_Y_PIN = 33    # GPIO33 - ADC1
ACC_Z_PIN = 36    # GPIO36 - ADC1 (input only)

# Buttons (DFRobot digital modules)
BUTTON_PINS = {
    "b1": 16,
    "b2": 17,
    "b3": 19,
}

# Ultrasonic (HC-SR04)
ULTRASONIC_TRIG_PIN = 5    # OUTPUT - GPIO5
ULTRASONIC_ECHO_PIN = 18   # INPUT - GPIO18 (WITH VOLTAGE DIVIDER!)

# Heart rate sensor (MAX30100)
HEART_RATE_SCL_PIN = 22
HEART_RATE_SDA_PIN = 21


# ===============================
# READ INTERVALS (ms)
# ===============================

TEMP_INTERVAL = 1000       # temperature read interval
CO_INTERVAL = 1000         # CO read interval
ACC_INTERVAL = 100         # accelerometer read interval
BUTTON_INTERVAL = 50       # button scan interval
HEART_RATE_INTERVAL = 1000 # heart rate read interval
ULTRASONIC_INTERVAL = 100  # ultrasonic read interval

# Logic evaluation interval (warning/danger)
LOGIC_INTERVAL = 200


# ===============================
# SOGLIE ISTANTANEE
# ===============================

# CO in PPM (aria in casa)
CO_CRITICAL_PPM = 50.0     # sopra questo valore la situazione è critica

# Temperatura di casa (°C) - range di comfort/sicurezza
TEMP_MIN_SAFE = 10.0
TEMP_MAX_SAFE = 35.0

# Heart rate e SpO2 per anziano
BPM_LOW_THRESHOLD = 50
BPM_HIGH_THRESHOLD = 120
SPO2_THRESHOLD = 90


# ===============================
# LOGICA TEMPORALE WARNING / DANGER
# ===============================

# Flag per attivare/disattivare il monitoraggio di ogni sensore
ALARM_CO_ENABLED = True
ALARM_TEMP_ENABLED = True
ALARM_HEART_ENABLED = True
ALARM_ULTRASONIC_ENABLED = True

# CO (PPM)
CO_WARNING_TIME_MS = 5000       # CO critico per almeno 5s -> warning
CO_DANGER_TIME_MS = 30000       # CO critico per almeno 30s -> danger
CO_RECOVERY_TIME_MS = 10000     # CO normale per 10s -> back to normal

# Temperatura
TEMP_WARNING_TIME_MS = 10000    # fuori range per 10s -> warning
TEMP_DANGER_TIME_MS = 60000     # fuori range per 60s -> danger
TEMP_RECOVERY_TIME_MS = 15000   # dentro range per 15s -> normal

# Heart rate / SpO2
HR_WARNING_TIME_MS = 10000      # valori anomali per 10s -> warning
HR_DANGER_TIME_MS = 60000       # valori anomali per 60s -> danger
HR_RECOVERY_TIME_MS = 15000     # valori normali per 15s -> normal

# Ultrasuoni (presenza davanti a cancello/porta)
ULTRASONIC_PRESENCE_DISTANCE_CM = 50.0  # presenza se più vicino di così
ULTRASONIC_WARNING_TIME_MS = 2000       # presenza per 2s -> warning
ULTRASONIC_DANGER_TIME_MS = 10000       # presenza per 10s -> danger
ULTRASONIC_RECOVERY_TIME_MS = 5000      # assenza per 5s -> normal
