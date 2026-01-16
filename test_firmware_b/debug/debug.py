from time import ticks_ms  # type: ignore

# Remote logging (optional, for centralized monitoring)
_remote_log = None

# Per-channel log flags. '*' is the default fallback. All enabled by default.
# Hierarchy: sensor.<name>.<type>, actuator.<name>.<type>, communication.<board>.<type>, alarm.<type>, core.<type>
_log_flags = {"*": True}


def set_log_enabled(name, enabled=True):
    """Enable/disable logs for a specific channel or hierarchy.
    
    Examples:
      set_log_enabled("actuator.servo", False)      # Disable all servo logs
      set_log_enabled("actuator.servo.gate", False) # Disable only servo gate logs
      set_log_enabled("communication.b", False)     # Disable all B communication logs
      set_log_enabled("alarm", False)               # Disable all alarm logs
    """
    _log_flags[name] = bool(enabled)


def set_all_logs(enabled=True):
    """Enable/disable all logs via wildcard."""
    _log_flags["*"] = bool(enabled)


def is_log_enabled(name):
    """Check if a channel is allowed to log using hierarchical prefix matching.
    
    Logic:
      1. Exact match: if "actuator.servo.gate" in flags, use that value
      2. Prefix match: if "actuator.servo" in flags, use that (matches "actuator.servo.gate")
      3. Prefix match: if "actuator" in flags, use that (matches "actuator.servo.gate")
      4. Wildcard default: use "*" if no other match
    """
    # Exact match
    if name in _log_flags:
        return _log_flags[name]
    
    # Prefix matching: check all flag names to find longest matching prefix
    # This allows hierarchical control (more specific flags override less specific)
    best_match_len = 0
    best_match_value = None
    
    for flag_name in _log_flags.keys():
        if flag_name != "*" and name.startswith(flag_name) and (name[len(flag_name):len(flag_name)+1] in (".", "")):
            # name starts with flag_name and either ends there or has a dot next
            if len(flag_name) > best_match_len:
                best_match_len = len(flag_name)
                best_match_value = _log_flags[flag_name]
    
    if best_match_value is not None:
        return best_match_value
    
    # Wildcard default
    return _log_flags.get("*", True)


def get_log_flags():
    """Return current log flag map (copy) for diagnostics."""
    return dict(_log_flags)


def init_remote_logging(device_id):
    """Initialize remote UDP logging for centralized monitoring.
    
    Args:
        device_id: 'A' for ESP32-A, 'B' for ESP32-B
    """
    global _remote_log
    try:
        from debug import remote_log
        if remote_log.init(device_id):
            _remote_log = remote_log
            print("debug: Remote logging enabled (device {})".format(device_id))
        else:
            print("debug: Remote logging disabled")
    except Exception as e:
        print("debug: Remote logging not available: {}".format(e))


def log(name, message):
    """Simple logging function for firmware with hierarchical per-channel flags."""
    if not is_log_enabled(name):
        return

    timestamp = ticks_ms()
    log_line = "[{}ms] [{}] {}".format(timestamp, name, message)
    
    # Always print to serial when enabled
    print(log_line)
    
    # Also send via UDP if remote logging is enabled
    if _remote_log and _remote_log.is_enabled():
        _remote_log.send_log(name, message)

