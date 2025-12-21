# State module for test firmware

sensor_data = {
    "temperature": None,
    "co": None,
    "acc": {"x": 0, "y": 0, "z": 0},
    "heart_rate": {"bpm": None, "spo2": None},
    "ultrasonic_distance_cm": None
}

button_state = {
    "b1": False,
    "b2": False,
    "b3": False
}
