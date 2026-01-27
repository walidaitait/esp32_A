"""Configuration package for ESP32 firmware.

Imported by: main.py, core.*, sensors.*, actuators.*, communication.*, logic.*
Imports: (package container, imports config submodules)

Contains configuration modules:
- config: Main configuration loaded from config.json (pins, intervals, thresholds, etc.)
- wifi_config: WiFi credentials and MQTT/Adafruit IO settings

Configuration is loaded at import time from JSON files.
Changes to JSON require reboot to take effect.

This __init__.py file is intentionally minimal to allow selective imports.
"""
