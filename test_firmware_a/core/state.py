"""Shared state module for ESP32-A (Sensor Board).

Imported by: main.py, core.sensor_loop, logic.alarm_logic, sensors.*, 
             communication.espnow_communication, communication.command_handler
Imports: None (pure data module)

This module provides centralized state storage accessible by all subsystems.
Contains:
- Raw sensor readings (temperature, CO, heart rate, ultrasonic, accelerometer)
- Button states (3 buttons: b1, b2, b3)
- Per-sensor alarm levels (normal/warning/danger for CO, temp, heart rate)
- Overall system alarm state (aggregated from all sensors)
- Gate automation state (presence detection, gate open/closed status)
- Received actuator state from ESP32-B via ESP-NOW
- System control flags (OTA, reboot requests)
- Simulation mode flag

All state variables are mutable dictionaries/values to allow updates from anywhere.
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
    "source": None,        # co | temp | heart | manual | None
    "sos_mode": False,  # True when SOS active (from app or board B button) - prevents auto-clear by sensors
}

# Gate control state (for presence-based automation)
gate_state = {
    "presence_detected": False,     # True when ultrasonic detects presence < threshold
    "gate_open": False,             # True when gate is open (servo at 90°) - synced with app and ESP32-B
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
    "sos_mode": False,
    "last_update": None,
    "is_stale": True,  # True if no update received within timeout
}

# System control flags (set by remote commands)
system_control = {
    "ota_update_requested": False,
    "reboot_requested": False,
}

# Simulation mode tracking
simulation_mode = False
