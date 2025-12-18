from time_sync import get_datetime_string

debug_flags = {
    
    "buttons": True,
    "commands": True,
    "config": True,
    "logic": True,
    "main": True,
    "mqtt_client": True,
    "sensors_accelerometer": True,
    "sensors_co": True,
    "sensors_temperature": True,
    "sensors_ultrasonic": True,
    "simple": False,
    "simulate_sensors": True,
    "state": True,
    "timers": True
}

def log(name, message):
    if debug_flags.get(name, False):
        timestamp = get_datetime_string()
        print("[{}] [{}] {}".format(timestamp, name, message))

