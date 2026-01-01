"""Low-level communication management for ESP32-B.

Handles:
- UDP beacon discovery (auto-discovery of ESP32-A)
- HTTP server for receiving commands
- Packet tracking and validation
- Connection status monitoring

Does NOT handle command execution - that's in command_handler.py
"""

import socket
import json
import time
from debug import log
from timers import elapsed
import state
from comms.device_id import DeviceDiscovery, get_device_key

# ===========================
# MODULE STATE
# ===========================

_initialized = False
_device_discovery = None
_http_socket = None

# Packet tracking (detects missing packets from A)
_last_received_packet_id = -1
_expected_next_id = 0

# Command callback (set by command_handler)
_command_callback = None


# ===========================
# INITIALIZATION
# ===========================

def init_communication():
    """Initialize communication system with auto-discovery.
    
    Starts HTTP server to receive commands from ESP32-A.
    No hardcoded IP/MAC needed - uses UDP beacon for discovery.
    Loads last received packet ID from persistent state.
    
    Returns:
        True if initialization successful, False otherwise
    """
    global _initialized, _device_discovery, _http_socket
    global _last_received_packet_id, _expected_next_id
    
    try:
        # Load last received packet ID from state (survives if A reboots)
        if hasattr(state, 'last_packet_id_from_a') and state.last_packet_id_from_a >= 0:
            _last_received_packet_id = state.last_packet_id_from_a
            _expected_next_id = _last_received_packet_id + 1
            log("comm", "Resumed packet tracking: expecting packet #{}".format(_expected_next_id))
        else:
            log("comm", "Starting fresh packet tracking from 0")
        
        # Initialize device discovery
        log("comm", "═══════════════════════════════════════════════")
        log("comm", "Starting UDP beacon discovery for ESP32-A...")
        log("comm", "Broadcasting on port {}".format(37020))
        _device_discovery = DeviceDiscovery(is_device_b=True)
        
        # Create HTTP server socket
        _http_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _http_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        _http_socket.bind(('0.0.0.0', 80))
        _http_socket.listen(1)
        _http_socket.settimeout(0.5)  # Non-blocking with timeout
        
        _initialized = True
        log("comm", "HTTP server listening on port 80")
        log("comm", "Auto-discovery enabled - waiting for ESP32-A beacon...")
        log("comm", "═══════════════════════════════════════════════")
        return True
        
    except Exception as e:
        log("comm", "Init failed: {}".format(e))
        return False


# ===========================
# COMMAND CALLBACK REGISTRATION
# ===========================

def register_command_callback(callback):
    """Register callback function to handle received commands.
    
    Args:
        callback: Function(command, params) that executes the command
    """
    global _command_callback
    _command_callback = callback
    log("comm", "Command callback registered")


# ===========================
# PACKET VALIDATION
# ===========================

def _validate_packet(payload):
    """Validate received packet structure and sequence ID.
    
    Args:
        payload: Parsed JSON payload
        
    Returns:
        True if valid, False otherwise
    """
    global _last_received_packet_id, _expected_next_id
    
    # Check device key
    device_key = payload.get("device_key")
    if device_key != get_device_key(is_device_b=False):
        log("comm", "ERROR: Invalid device key: {}".format(device_key))
        return False
    
    # Extract and validate packet ID
    packet_id = payload.get("packet_id")
    if packet_id is None:
        log("comm", "ERROR: Packet missing ID field")
        return False
    
    # Check for missing packets
    if _last_received_packet_id >= 0:  # Not first packet
        expected_id = _last_received_packet_id + 1
        
        if packet_id != expected_id:
            # Packet(s) missing!
            if packet_id > expected_id:
                missing_count = packet_id - expected_id
                log("comm", "ERROR: Missing {} packet(s)! Expected ID {}, got {}".format(
                    missing_count, expected_id, packet_id
                ))
            elif packet_id < expected_id:
                log("comm", "WARNING: Received old packet ID {} (expected {})".format(
                    packet_id, expected_id
                ))
    
    # Update packet tracking
    _last_received_packet_id = packet_id
    _expected_next_id = packet_id + 1
    
    # Save to state (survives if A reboots)
    state.last_packet_id_from_a = packet_id
    
    return True


# ===========================
# HTTP REQUEST HANDLING
# ===========================

def _handle_http_request(client_socket):
    """Handle incoming HTTP request from ESP32-A.
    
    Args:
        client_socket: Connected client socket
    """
    try:
        # Read request
        request = client_socket.recv(2048).decode('utf-8')
        
        # Parse HTTP headers
        lines = request.split('\r\n')
        if not lines:
            return
        
        method_line = lines[0]
        
        # Only accept POST to /command
        if not method_line.startswith('POST /command'):
            # Send 404
            response = "HTTP/1.1 404 Not Found\r\n\r\n"
            client_socket.send(response.encode())
            return
        
        # Extract JSON body
        body_start = request.find('\r\n\r\n')
        if body_start == -1:
            return
        
        json_str = request[body_start + 4:]
        
        # Parse JSON
        payload = json.loads(json_str)
        
        # Validate packet
        if not _validate_packet(payload):
            # Send 400 Bad Request
            response = "HTTP/1.1 400 Bad Request\r\n\r\n"
            client_socket.send(response.encode())
            return
        
        packet_id = payload.get("packet_id")
        command = payload.get("command")
        params = payload.get("params", {})
        
        log("comm", "┌─────────────────────────────────────────────")
        log("comm", "│ ✓ Received packet #{} from ESP32-A".format(packet_id))
        log("comm", "│ Command: '{}'".format(command))
        log("comm", "│ Params: {}".format(params))
        log("comm", "└─────────────────────────────────────────────")
        
        # Execute command via callback
        if _command_callback:
            _command_callback(command, params)
        else:
            log("comm", "WARNING: No command callback registered!")
        
        # Mark as connected
        if _device_discovery:
            _device_discovery.mark_connected()
        
        # Send 200 OK
        response = "HTTP/1.1 200 OK\r\n\r\n"
        client_socket.send(response.encode())
        
    except Exception as e:
        log("comm", "Request handling error: {}".format(e))
        try:
            response = "HTTP/1.1 500 Internal Server Error\r\n\r\n"
            client_socket.send(response.encode())
        except:
            pass


# ===========================
# UPDATE LOOP
# ===========================

def update():
    """Update communication system (discovery, HTTP server).
    
    Called from main loop. Non-blocking - uses socket timeout.
    Handles beacon sending/receiving and incoming HTTP requests.
    """
    global _device_discovery, _http_socket
    
    if not _initialized:
        return
    
    # Update discovery (beacon listening + sending)
    if _device_discovery:
        _device_discovery.update_discovery()
    
    # Check for incoming HTTP requests (non-blocking)
    if _http_socket:
        try:
            client, addr = _http_socket.accept()
            client.settimeout(2.0)
            _handle_http_request(client)
            client.close()
        except OSError:
            # Timeout or no connection - this is normal
            pass
        except Exception as e:
            log("comm", "Accept error: {}".format(e))


# ===========================
# STATUS QUERIES
# ===========================

def is_connected():
    """Check if ESP32-A is reachable and connection is established."""
    global _device_discovery
    
    if not _initialized or not _device_discovery:
        return False
    
    return _device_discovery.is_connected()


def get_discovered_ip():
    """Get the discovered IP address of ESP32-A.
    
    Returns:
        IP address string or None if not discovered yet
    """
    global _device_discovery
    
    if not _initialized or not _device_discovery:
        return None
    
    return _device_discovery.get_other_ip()
