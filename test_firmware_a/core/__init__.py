"""Core package for ESP32 firmware.

Imported by: main.py, sensors.*, actuators.*, communication.*, logic.*
Imports: (package container, imports submodules)

Contains fundamental system modules:
- state: Shared state storage (sensor data, alarm levels, system flags)
- timers: Non-blocking interval timing with user override support
- wifi: WiFi connection management
- sensor_loop: Sensor reading orchestration (Board A only)
- actuator_loop: Actuator control orchestration (Board B only)

This __init__.py file is intentionally minimal to allow selective imports.
"""
