import time

# Remote logging (optional, for centralized monitoring)
_remote_log = None

def init_remote_logging(device_id):
    """Initialize remote UDP logging for centralized monitoring.
    
    Args:
        device_id: 'A' for ESP32-A, 'B' for ESP32-B
    """
    global _remote_log
    try:
        import remote_log
        if remote_log.init(device_id):
            _remote_log = remote_log
            print("debug: Remote logging enabled (device {})".format(device_id))
        else:
            print("debug: Remote logging disabled")
    except Exception as e:
        print("debug: Remote logging not available: {}".format(e))


def log(name, message):
    """Simple logging function for firmware.
    
    Logs to both serial console and UDP (if remote logging enabled).
    """
    timestamp = time.ticks_ms()
    log_line = "[{}ms] [{}] {}".format(timestamp, name, message)
    
    # Always print to serial
    print(log_line)
    
    # Also send via UDP if remote logging is enabled
    if _remote_log and _remote_log.is_enabled():
        _remote_log.send_log(name, message)

