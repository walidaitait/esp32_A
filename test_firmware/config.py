# ===============================
# TEST FIRMWARE - CONFIGURATION
# ===============================

# --------- ANALOG SENSORS (ADC1 ONLY) ---------

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
    "b3": 19
}

# --------- ULTRASONIC SENSOR (HC-SR04) ---------
ULTRASONIC_TRIG_PIN = 5    # OUTPUT - GPIO5
ULTRASONIC_ECHO_PIN = 18   # INPUT - GPIO18 (WITH VOLTAGE DIVIDER!)

# --------- HEART RATE SENSOR (MAX30100) ---------
HEART_RATE_SCL_PIN = 22
HEART_RATE_SDA_PIN = 21

# --------- TIMING (milliseconds) ---------
TEMP_INTERVAL = 1000      # temperature read interval
CO_INTERVAL = 1000        # CO read interval
ACC_INTERVAL = 100        # accelerometer read interval
BUTTON_INTERVAL = 50      # button scan interval
HEART_RATE_INTERVAL = 1000  # heart rate read interval
ULTRASONIC_INTERVAL = 100   # ultrasonic read interval
