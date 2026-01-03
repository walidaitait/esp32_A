"""
Shared state for actuator firmware (ESP32-B).

Contains the current state of LED modules, servo, LCD, buzzer and DFPlayer.
"""

actuator_state = {
    "leds": {
        "green": False,
        "blue": False,
        "red": False,
    },
    # Logical mode of LEDs ("off", "on", "blinking")
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

# Packet tracking: survives reboot of A (memory of last packet IDs)
last_packet_id_from_a = -1  # Last packet ID received from A
last_packet_id_sent_to_a = -1  # Last packet ID sent to A (if we send back)
