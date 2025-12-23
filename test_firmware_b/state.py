"""
Stato condiviso per il TEST FIRMWARE attuatori (ESP32-B).

Contiene lo stato corrente dei moduli LED, servo, LCD, buzzer e DFPlayer.
"""

actuator_state = {
    "leds": {
        "green": False,
        "blue": False,
        "red": False,
    },
    # Modalita logica dei LED ("off", "on", "blinking")
    "led_modes": {
        "green": "off",
        "blue": "off",
        "red": "off",
    },
    "servo": {
        "angle": None,
        "moving": False,
    },
    "lcd": {
        "line1": "",
        "line2": "",
    },
    "buzzer": {
        "active": False,
    },
    "audio": {
        "playing": False,
        "last_cmd": None,
    },
}
