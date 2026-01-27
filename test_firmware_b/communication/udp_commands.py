"""UDP command listener for ESP32-B development and testing.

Imported by: main.py
Imports: socket, ujson, debug.debug, communication.command_handler

Listens for incoming UDP commands on port 37022 and passes them to command_handler.
Uses non-blocking socket to integrate seamlessly with main loop.

Primary use cases:
- Development testing (send_command.py tool)
- Quick actuator control for demos
- System control without MQTT
- Emergency commands if MQTT is down

Protocol: JSON messages on UDP port 37022
{
    "target": "B",
    "command": "led",
    "args": ["green", "on"]
}
"""

import socket
try:
    import ujson as json  # type: ignore  # MicroPython
except ImportError:
    import json  # Fallback
from debug.debug import log
from communication import command_handler

# Configuration
UDP_COMMAND_PORT = 37022  # Port to listen for commands
_socket = None
_initialized = False
_messages_received = 0  # Track total messages received
_update_cycles = 0      # Track update() calls for diagnostics


def init():
    """Initialize UDP command listener (non-blocking socket)."""
    global _socket, _initialized
    
    try:
        _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _socket.bind(('', UDP_COMMAND_PORT))
        _socket.setblocking(False)  # Non-blocking for integration with main loop
        
        _initialized = True
        log("communication.udp_cmd", "UDP command listener started on port {}".format(UDP_COMMAND_PORT))
        log("communication.udp_cmd", "Ready to receive commands from UDP clients")
        return True
    
    except Exception as e:
        log("communication.udp_cmd", "Init failed: {}".format(e))
        _initialized = False
        return False


def update():
    """Check for incoming commands (non-blocking).
    
    Should be called repeatedly from main loop.
    """
    if not _initialized or not _socket:
        return
    
    global _update_cycles, _messages_received
    _update_cycles += 1
    
    try:
        # Try to receive data (non-blocking)
        data, addr = _socket.recvfrom(1024)
        
        if not data:
            return
        
        # Successfully received data
        _messages_received += 1
        
        # Decode and parse JSON
        try:
            message = data.decode('utf-8')
            cmd_data = json.loads(message)
            
            # Validate message structure
            if not isinstance(cmd_data, dict):
                log("communication.udp_cmd", "Invalid message format (not a dict)")
                return
            
            # Check if this command is for us (target B)
            target = cmd_data.get("target", "").upper()
            if target != "B":
                # Not for us, ignore silently
                return
            
            command = cmd_data.get("command", "")
            args = cmd_data.get("args", [])
            
            if not command:
                log("communication.udp_cmd", "No command in message")
                return
            
            log("communication.udp_cmd", "RX: {} {} from {}".format(command, args, addr[0]))
            
            # Handle command
            response = command_handler.handle_command(command, args)
            
            # Log response
            if response.get("success"):
                log("communication.udp_cmd", "OK: {}".format(response.get("message")))
            else:
                log("communication.udp_cmd", "ERROR: {}".format(response.get("message")))
            
            # Optionally send response back to sender
            _send_response(addr, response)
        
        except json.JSONDecodeError as e:
            log("communication.udp_cmd", "JSON decode error: {}".format(e))
        except Exception as e:
            log("communication.udp_cmd", "Error processing command: {}".format(e))
    
    except OSError as e:
        # No data available (EAGAIN/EWOULDBLOCK) - this is normal for non-blocking
        # Codes: 11 (Unix EAGAIN), 10035 (Windows WSAEWOULDBLOCK), 107 (Unix ENOTCONN)
        if e.args[0] not in (11, 10035, 107):
            log("communication.udp_cmd", "Socket error {}: {}".format(e.args[0] if e.args else "?", e))


def _send_response(addr, response):
    """Send response back to command sender.
    
    Args:
        addr: Address tuple (ip, port) of sender
        response: Response dict from command_handler
    """
    try:
        if _socket is None:
            return
        response_json = json.dumps(response)
        _socket.sendto(response_json.encode('utf-8'), addr)
    except Exception as e:
        log("communication.udp_cmd", "Failed to send response: {}".format(e))


def is_initialized():
    """Check if UDP command listener is initialized."""
    return _initialized


def get_stats():
    """Get UDP communication statistics for diagnostics.
    
    Returns:
        dict with communication stats
    """
    return {
        "initialized": _initialized,
        "messages_received": _messages_received,
        "update_cycles": _update_cycles,
        "port": UDP_COMMAND_PORT
    }
