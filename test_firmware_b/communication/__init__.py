"""Communication package for ESP32-B - Inter-board and external protocols.

Imported by: main.py
Provides: espnow_communication, udp_commands, command_handler

Communication subsystems:
- espnow_communication: Receives sensor data from Board A via ESP-NOW
- udp_commands: Development command interface via UDP
- command_handler: Transport-agnostic command interpreter and executor

Board B acts as ESP-NOW server, receiving sensor state and alarm levels from Board A.
Does NOT forward data to Node-RED/MQTT - Board A handles all northbound communication.
"""
