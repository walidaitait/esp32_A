"""Debug package for ESP32-B - Logging and diagnostics.

Imported by: All modules
Provides: debug (hierarchical logging), remote_log (UDP logging to PC)

Debug subsystems:
- debug: Main logging with channel-based filtering
- remote_log: UDP broadcast to development PC (port 37021)

Logging hierarchy: actuator.*, communication.*, logic.*, core.*
Control via set_log_enabled() and set_all_logs().
"""
# Debug module
