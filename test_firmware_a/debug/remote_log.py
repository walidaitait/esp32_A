"""Remote UDP logging for centralized monitoring.

Imported by: debug.debug
Imports: socket, network (MicroPython)

Sends log messages to PC via UDP broadcast for real-time monitoring.
Allows viewing logs from both ESP32-A and ESP32-B simultaneously in one console.

Features:
- UDP broadcast to all devices on local network
- Device ID prefix ('A' or 'B') for multi-board identification
- Non-blocking sends (fire-and-forget)
- Graceful degradation if WiFi unavailable
- Works with log_listener.py tool on PC

Setup:
1. Run log_listener.py on PC (listens on port 37021)
2. ESP32 boards send UDP broadcasts to 255.255.255.255:37021
3. PC captures and displays logs from all devices

Network requirements:
- ESP32 and PC must be on same local network
- Firewall must allow UDP broadcast on port 37021
- WiFi must be connected before enabling remote logging

Log format: "[DEVICE_ID][module] message"
Example: "[A][sensor.co] CO reading: 15 PPM"
"""

import socket
import network

# UDP logging configuration
LOG_SERVER_PORT = 37021  # Port where PC listener is running
LOG_BROADCAST_IP = "255.255.255.255"  # Broadcast to all devices on network

# Module state
_udp_socket = None
_device_id = None  # 'A' or 'B'
_enabled = False


def init(device_id):
    """Initialize remote logging.
    
    Args:
        device_id: 'A' for ESP32-A (sensors), 'B' for ESP32-B (actuators)
    """
    global _udp_socket, _device_id, _enabled
    
    _device_id = device_id
    
    try:
        # Check if WiFi is connected
        wlan = network.WLAN(network.STA_IF)
        if not wlan.isconnected():
            print("remote_log: WiFi not connected, remote logging disabled")
            _enabled = False
            return False
        
        # Create UDP socket for broadcasting
        _udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        _enabled = True
        print("remote_log: UDP logging enabled (device {})".format(_device_id))
        return True
        
    except Exception as e:
        print("remote_log: Init failed: {}".format(e))
        _enabled = False
        return False


def send_log(module, message):
    """Send log message via UDP to PC listener.
    
    Args:
        module: Module name (e.g., "main", "comm", "sensors")
        message: Log message string
    """
    global _udp_socket, _device_id, _enabled
    
    if not _enabled or not _udp_socket:
        return
    
    try:
        # Format: "[DEVICE_ID][module] message"
        log_line = "[{}][{}] {}".format(_device_id, module, message)
        data = log_line.encode('utf-8')
        
        # Broadcast to network
        _udp_socket.sendto(data, (LOG_BROADCAST_IP, LOG_SERVER_PORT))
        
    except Exception as e:
        # Don't print to avoid recursion, just disable
        _enabled = False


def is_enabled():
    """Check if remote logging is enabled."""
    return _enabled
