"""
Configuration for actuator firmware on ESP32-B.

Here we define pins and general settings for the modules
(LED, servo, LCD, buzzer, DFPlayer+speaker).
"""

# ===============================
# INTER-DEVICE COMMUNICATION
# ===============================

# NOTE: No hardcoded MAC or IP needed!
# Auto-discovery via UDP beacon - plug and play

# Communication update frequency (ms)
COMM_UPDATE_INTERVAL_MS = 100

# DFRobot LED modules (DFR0021-G/B/R)
# Module VCC at 5V, common GND, SIG pin to GPIO at 3.3V logic levels.
LED_PINS = {
    "green": 16,   # GPIO16
    "blue": 17,    # GPIO17
    "red": 19,     # GPIO19
}

# SG90 9g Servo - VCC 5V, common GND, PWM signal 3.3V
SERVO_PIN = 23     # GPIO23
SERVO_MAX_ANGLE = 180  # Maximum angle in degrees

# LCD 1602A with I2C backpack (GND, VCC, SDA, SCL)
# VCC 5V, common GND, I2C bus at 3.3V (GPIO21/22).
LCD_SDA_PIN = 21   # GPIO21
LCD_SCL_PIN = 22   # GPIO22
LCD_I2C_ID = 0     # I2C(0) on ESP32 in MicroPython

# DFRobot Passive buzzer (3 pin: VCC, SIG, GND)
# Connect SIG to GPIO25, VCC to 5V and common GND. The SIG pin is driven at
# 3.3V directly from GPIO via PWM.
BUZZER_PIN = 25    # GPIO25 (signal)

# DFPlayer Mini (VCC 5V, common GND, UART at 3.3V)
DFPLAYER_UART_ID = 1        # UART(1) on ESP32
DFPLAYER_TX_PIN = 27        # ESP32 TX -> DFPlayer RX
DFPLAYER_RX_PIN = 26        # ESP32 RX <- DFPlayer TX
DFPLAYER_DEFAULT_VOLUME = 20  # 0-30
