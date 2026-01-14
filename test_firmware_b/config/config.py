"""Configuration for actuator firmware on ESP32-B.

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

SIMULATE_ACTUATORS = _config.get('simulate_actuators', False)

# ===============================
# ACTUATOR ENABLED FLAGS
# ===============================

actuators_config = _config.get('actuators', {})
LEDS_ENABLED = actuators_config.get('leds', {}).get('enabled', True)
SERVO_ENABLED = actuators_config.get('servo', {}).get('enabled', True)
LCD_ENABLED = actuators_config.get('lcd', {}).get('enabled', True)
BUZZER_ENABLED = actuators_config.get('buzzer', {}).get('enabled', True)
AUDIO_ENABLED = actuators_config.get('audio', {}).get('enabled', True)

# ===============================
# BUTTON (Physical button on GPIO18)
# ===============================
BUTTON_ENABLED = _config.get('button_enabled', True)
button_config = _config.get('button', {})
BUTTON_PIN = button_config.get('pin', 18)
BUTTON_INTERVAL = button_config.get('interval_ms', 50)

# ===============================
# LED MODULES (DFRobot DFR0021-G/B/R)
# ===============================
# VCC 5V, common GND, SIG pins at 3.3V logic levels.
LED_PINS = _config.get('leds', {
    "green": 16,
    "blue": 17,
    "red": 19,
})


# ===============================
# SERVO (SG90 9g)
# ===============================
# VCC 5V, common GND, PWM signal 3.3V.
servo_config = _config.get('servo', {})
SERVO_PIN = servo_config.get('pin', 23)
SERVO_MAX_ANGLE = servo_config.get('max_angle', 180)


# ===============================
# LCD 1602A WITH I2C BACKPACK
# ===============================
# VCC 5V, common GND, I2C bus at 3.3V (GPIO21/22).
lcd_config = _config.get('lcd', {})
LCD_SDA_PIN = lcd_config.get('sda_pin', 21)
LCD_SCL_PIN = lcd_config.get('scl_pin', 22)
LCD_I2C_ID = lcd_config.get('i2c_id', 0)


# ===============================
# PASSIVE BUZZER (DFRobot)
# ===============================
# SIG to GPIO25, VCC 5V, common GND. SIG driven at 3.3V PWM.
buzzer_config = _config.get('buzzer', {})
BUZZER_PIN = buzzer_config.get('pin', 25)


# ===============================
# DFPLAYER MINI + SPEAKER
# ===============================
# VCC 5V, common GND, UART at 3.3V levels.
dfplayer_config = _config.get('dfplayer', {})
DFPLAYER_UART_ID = dfplayer_config.get('uart_id', 1)
DFPLAYER_TX_PIN = dfplayer_config.get('tx_pin', 27)
DFPLAYER_RX_PIN = dfplayer_config.get('rx_pin', 26)
DFPLAYER_DEFAULT_VOLUME = dfplayer_config.get('default_volume', 20)

# ===============================
# GATE AUTOMATION
# ===============================
gate_config = _config.get('gate', {})
GATE_CLOSE_DELAY_MS = gate_config.get('close_delay_ms', 10000)

