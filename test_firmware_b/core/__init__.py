"""Core modules package for ESP32-B actuator firmware.

Imported by: main.py
Provides: state, timers, wifi, actuator_loop

Core subsystems:
- state: Shared state dictionaries for actuators and received sensor data
- timers: Non-blocking interval timing with user override support
- wifi: WiFi connection management for logging and OTA
- actuator_loop: Main orchestration loop for all actuator updates
"""
# Core module
