
sensor_data = {
    "temperature": None,
    "co": None,
    "acc": {"x": 0, "y": 0, "z": 0},
    "heart_rate": {"bpm": None, "spo2": None}
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
    "movement": False,
    "alarm_bpm": False,
    "alarm_spo2": False
}


alarm_state = {
    "level":"normal",
    "source":None
    }

tx_seq = 0

pending_ack = {
    "seq":None,
    "timestamp":0,
    "retries":0
}

def build_command():
    return {"alarm":alarm_state}


#ESP32 B output commands
output_commands = {
    "led_red": False,
    "led_green": False,
    "led_blue": False,
    "buzzer": False,
    "servo_angle": 0,
    "lcd_message": ""
}

