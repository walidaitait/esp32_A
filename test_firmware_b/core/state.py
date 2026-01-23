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
        "angle": 0,
        "moving": False,
    },
    "lcd": {
        "line1": "",
        "line2": "",
    },
    "buzzer": {
        "active": False,
        "alarm_muted": False,
    },
    "audio": {
        "playing": False,
        "last_cmd": None,
    },
    "button": False,
    "simulation_mode": False,
    "sos_mode": False,  # Emergency SOS call active
}

# Packet tracking: survives reboot of A (memory of last packet IDs)
last_packet_id_from_a = -1  # Last packet ID received from A
last_packet_id_sent_to_a = -1  # Last packet ID sent to A (if we send back)

# Received sensor state from ESP32-A (updated via ESP-NOW)
received_sensor_state = {
    "temperature": None,
    "co": None,
    "heart_rate_bpm": None,
    "heart_rate_spo2": None,
    "ultrasonic_distance": None,
    "button_b1": False,
    "button_b2": False,
    "button_b3": False,
    "presence_detected": False,    # Gate control: presence detected from ultrasonic
    "alarm_level": "normal",       # Alarm level (normal | warning | danger)
    "alarm_source": None,          # Alarm source (co | temp | heart)
    "last_update": None,
    "is_stale": True,              # True if no update received within timeout
}

# System control flags (set by remote commands)
system_control = {
    "ota_update_requested": False,
    "reboot_requested": False,
}
