"""Sensors package for ESP32-A (Sensor Board).

Imported by: core.sensor_loop, main.py
Imports: (package container, imports sensor submodules)

Contains individual sensor driver modules:
- temperature: DS18B20 temperature sensor (OneWire)
- co: MQ-7 carbon monoxide sensor (analog ADC)
- heart_rate: MAX30100 heart rate + SpO2 sensor (I2C)
- ultrasonic: HC-SR04 distance/presence sensor
- buttons: Digital input buttons (3x)
- accelerometer: MPU6050/similar (I2C) - optional
- simulation: Fake sensor data generator for testing without hardware

Each sensor module provides init_*() and read_*() functions.
All reads are non-blocking and update core.state.sensor_data directly.

This __init__.py file is intentionally minimal to allow selective imports.
"""
