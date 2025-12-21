from time_sync import get_datetime_string

debug_flags = {
    # Keep only WiFi/MQTT visibility; everything else muted to avoid noise
    "mqtt_client": True,

    # Sensor logs (current module names)
    "temperature": False,
    "ultrasonic": False,
    "heart_rate": False,
    "co": False,
    "accelerometer": False,

    # Disabled logs
    "buttons": False,
    "commands": False,
    "config": False,
    "logic": False,
    "main": False,
    "simple": False,
    "simulate_sensors": False,
    "state": False,
    "timers": False,
    "espnow": False,
    "alarm": False,
    "hooks": False
}

def log(name, message):
    if debug_flags.get(name, False):
        timestamp = get_datetime_string()
        print("[{}] [{}] {}".format(timestamp, name, message))


def set_debug_flags(flags: dict):
    # Update multiple flags and always print the change for visibility
    timestamp = get_datetime_string()
    for name, enabled in flags.items():
        debug_flags[name] = bool(enabled)
    print("[{}] [debug] updated_flags={}".format(timestamp, flags))


def set_debug_flag(name: str, enabled: bool):
    set_debug_flags({name: enabled})

