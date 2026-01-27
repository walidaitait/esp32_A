"""Debug package for ESP32 firmware.

Imported by: All modules requiring logging
Imports: (package container, imports debug submodules)

Contains debugging and diagnostic tools:
- debug: Main logging system with hierarchical channel control
- remote_log: UDP-based remote logging for centralized monitoring

Logging is essential for:
- Real-time debugging via serial console
- Performance profiling (timestamps)
- Remote monitoring via log_listener.py tool
- Post-mortem analysis of crashes
- Alarm trigger diagnosis

This __init__.py file is intentionally minimal to allow selective imports.
"""
