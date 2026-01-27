"""Communication package for ESP32-A (Sensor Board).

Imported by: main.py
Imports: (package container, imports communication submodules)

Contains communication protocol modules:
- espnow_communication: ESP-NOW peer-to-peer with Board B (primary data channel)
- nodered_client: MQTT bridge to Node-RED and mobile app via Adafruit IO
- udp_commands: UDP command listener for remote control and testing
- command_handler: Command interpreter (transport-agnostic)

Communication architecture:
  ESP32-A (Sensors) <--ESP-NOW--> ESP32-B (Actuators)
        |
        +--MQTT--> Node-RED <--> Mobile App
        |
        +--UDP--> Development tools (send_command.py, log_listener.py)

This __init__.py file is intentionally minimal to allow selective imports.
"""
