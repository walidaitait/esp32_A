"""
Configurazione per TEST FIRMWARE attuatori su ESP32-B.

Qui definiamo pin, intervalli di aggiornamento e flag per abilitare/disabilitare
i singoli moduli di test (LED, servo, LCD, buzzer, DFPlayer+speaker).
"""

# ===============================
# PIN ATTUATORI
# ===============================

# Moduli LED DFRobot (DFR0021-G/B/R)
# VCC dei moduli a 5V, GND comune, SIG collegato a GPIO a 3.3V logici.
LED_PINS = {
    "green": 16,   # GPIO16
    "blue": 17,    # GPIO17
    "red": 19,     # GPIO19
}

# Servo SG90 9g - VCC 5V, GND comune, segnale PWM 3.3V
SERVO_PIN = 23     # GPIO23

# LCD 1602A con backpack I2C (GND, VCC, SDA, SCL)
# VCC 5V, GND comune, bus I2C a 3.3V (GPIO21/22).
LCD_SDA_PIN = 21   # GPIO21
LCD_SCL_PIN = 22   # GPIO22
LCD_I2C_ID = 0     # I2C(0) su ESP32 in MicroPython

# Passive buzzer Sunfounder (2 pin)
# Collegare + al GPIO25 e - a GND. Pilotato a 3.3V direttamente dalla GPIO.
BUZZER_PIN = 25    # GPIO25

# DFPlayer Mini (VCC 5V, GND comune, UART a 3.3V)
DFPLAYER_UART_ID = 1        # UART(1) su ESP32
DFPLAYER_TX_PIN = 27        # ESP32 TX -> DFPlayer RX
DFPLAYER_RX_PIN = 26        # ESP32 RX <- DFPlayer TX
DFPLAYER_DEFAULT_VOLUME = 20  # 0-30

# ===============================
# FLAG DI ABILITAZIONE MODULI
# ===============================
# Per il test singolo del DISPLAY abilitiamo solo l'LCD

LED_TEST_ENABLED = False
SERVO_TEST_ENABLED = False
LCD_TEST_ENABLED = True
BUZZER_TEST_ENABLED = False
AUDIO_TEST_ENABLED = False    # DFPlayer + speaker

# ===============================
# INTERVALLI / PARAMETRI TEST (ms)
# ===============================

# LED: passo di "scansione" dei tre moduli
LED_STEP_INTERVAL_MS = 400

# Servo: sweep non bloccante
SERVO_MIN_ANGLE = 0
SERVO_MAX_ANGLE = 180
SERVO_STEP_DEG = 5
SERVO_STEP_INTERVAL_MS = 150

# LCD: cambio messaggio periodico
LCD_UPDATE_INTERVAL_MS = 2000

# Buzzer: beep ON/OFF
BUZZER_TOGGLE_INTERVAL_MS = 500

# Audio / DFPlayer
AUDIO_STATUS_PRINT_INTERVAL_MS = 3000
AUDIO_AUTOPLAY_ON_START = False   # Se True, parte subito una traccia di test
