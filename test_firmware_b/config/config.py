"""Configuration for actuator firmware on ESP32-B.

Defines pins and general settings for LED, servo, LCD, buzzer, and
DFPlayer modules.
"""

# ===============================
# LED MODULES (DFRobot DFR0021-G/B/R)
# ===============================
# VCC 5V, common GND, SIG pins at 3.3V logic levels.
LED_PINS = {
    "green": 16,   # GPIO16
    "blue": 17,    # GPIO17
    "red": 19,     # GPIO19
}


# ===============================
# SERVO (SG90 9g)
# ===============================
# VCC 5V, common GND, PWM signal 3.3V.
SERVO_PIN = 23           # GPIO23
SERVO_MAX_ANGLE = 180    # Maximum angle in degrees


# ===============================
# LCD 1602A WITH I2C BACKPACK
# ===============================
# VCC 5V, common GND, I2C bus at 3.3V (GPIO21/22).
LCD_SDA_PIN = 21         # GPIO21
LCD_SCL_PIN = 22         # GPIO22
LCD_I2C_ID = 0           # I2C(0) on ESP32 in MicroPython


# ===============================
# PASSIVE BUZZER (DFRobot)
# ===============================
# SIG to GPIO25, VCC 5V, common GND. SIG driven at 3.3V PWM.
BUZZER_PIN = 25          # GPIO25 (signal)


# ===============================
# DFPLAYER MINI + SPEAKER
# ===============================
# VCC 5V, common GND, UART at 3.3V levels.
DFPLAYER_UART_ID = 1         # UART(1) on ESP32
DFPLAYER_TX_PIN = 27         # ESP32 TX -> DFPlayer RX
DFPLAYER_RX_PIN = 26         # ESP32 RX <- DFPlayer TX
DFPLAYER_DEFAULT_VOLUME = 20 # 0-30
