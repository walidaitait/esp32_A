
sensor_data = {
    "temperature": None,
    "co": None,
    "acc": {"x": 0, "y": 0, "z": 0}
}

button_state = {
    "b1": False,
    "b2": False,
    "b3": False
}

ultrasonic_distance_cm = None

system_state = {
    "alarm_co": False,
    "alarm_temp": False,
    "movement": False
}

#ESP32 B output commands
output_commands = {
    "led_red": False,
    "led_green": False,
    "led_blue": False,
    "buzzer": False,
    "servo_angle": 0,
    "lcd_message": ""
}

