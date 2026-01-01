"""
Shared state for actuator firmware (ESP32-B).

Contains the current state of LED modules, servo, LCD, buzzer and DFPlayer.
Also includes communication state for sensor data from ESP32-A.
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

# Communication state: sensor data received from ESP32-A
communication_state = {
    "last_update": None,
    "sensor_data": {
        "temperature": None,
        "co": None,
        "distance": None,
        "heart_rate": None,
        "spo2": None,
        "alarm_level": None,
        "alarm_source": None,
        "timestamp": None,
    },
}

# Packet tracking: survives reboot of A (memory of last packet IDs)
last_packet_id_from_a = -1  # Last packet ID received from A
last_packet_id_sent_to_a = -1  # Last packet ID sent to A (if we send back)
