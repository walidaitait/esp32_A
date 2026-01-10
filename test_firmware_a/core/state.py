"""Shared state for test firmware.

Contains raw sensor data, button states, and alarm levels computed by logic.
"""

sensor_data = {
    "temperature": None,
    "co": None,
    "heart_rate": {"ir": None, "red": None, "bpm": None, "spo2": None, "status": "Not initialized"},
    "ultrasonic_distance_cm": None,
    "ultrasonic_presence": False,  # True when something is detected within presence range
    "acc": {"x": None, "y": None, "z": None},
}

button_state = {
    "b1": False,
    "b2": False,
    "b3": False,
}

# Alarm levels per sensor (normal / warning / danger)
system_state = {
    "co_level": "normal",
    "temp_level": "normal",
    "heart_level": "normal",
}

# Overall system alarm state
alarm_state = {
    "level": "normal",   # normal | warning | danger
    "source": None,        # co | temp | heart | None
    "type": None,        # tipo di allarme (co, temp, heart)
}

# Gate control state (for presence-based automation)
gate_state = {
    "presence_detected": False,     # True when ultrasonic detects presence < threshold
    "gate_open": False,             # True when gate is open (servo at 90°)
    "last_presence_lost_ms": None,  # Timestamp when presence was last lost
}

# Last packet ID received from ESP32-B (for future bidirectional comm)
last_packet_id_received_from_b = -1

# Received actuator state from ESP32-B (updated via ESP-NOW)
received_actuator_state = {
    "leds": {
        "green": "unknown",
        "blue": "unknown",
        "red": "unknown",
    },
    "servo_angle": None,
    "lcd_line1": "",
    "lcd_line2": "",
    "buzzer": "unknown",
    "audio": "unknown",
    "last_update": None,
}

# System control flags (set by remote commands)
system_control = {
    "ota_update_requested": False,
    "reboot_requested": False,
}

# Simulation mode tracking
simulation_mode = False
