"""Logic package for ESP32-A (Sensor Board).

Imported by: core.sensor_loop
Imports: (package container, imports logic submodules)

Contains high-level decision logic modules:
- alarm_logic: Evaluates sensor thresholds and computes multi-level alarms
              (normal/warning/danger) with time-based windows and recovery

Board B has:
- emergency: SOS detection from button press patterns

This __init__.py file is intentionally minimal to allow selective imports.
"""
