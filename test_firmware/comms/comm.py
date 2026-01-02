"""Low-level communication management for ESP32-A.

Handles:
- UDP beacon discovery (auto-discovery of ESP32-B)
- HTTP client connection management
- Packet tracking (sequence IDs)
- Connection status monitoring

Does NOT handle command logic - that's in command_sender.py
"""

import json
import urequests #type: ignore
import time
from debug.debug import log
from core.timers import elapsed
from core import state
from comms.device_id import DeviceDiscovery, get_device_key

# ===========================
# MODULE STATE
# ===========================

_initialized = False
_device_discovery = None

# Packet tracking (persistent across reboots)
_current_packet_id = 0
_last_acked_packet_id = -1


# ===========================
# INITIALIZATION
# ===========================

def init_communication():
    """Initialize communication system with auto-discovery.
    
    No hardcoded IP/MAC needed - uses UDP beacon for discovery.
    Loads packet counter from persistent state.
    
    Returns:
        True if initialization successful, False otherwise
    """
    global _initialized, _device_discovery, _current_packet_id
    
    try:
        # Load last packet ID from state (survives reboots)
        if hasattr(state, 'last_packet_id_sent_to_b') and state.last_packet_id_sent_to_b >= 0:
            _current_packet_id = state.last_packet_id_sent_to_b + 1
            log("comm", "Resumed packet counter from state: {}".format(_current_packet_id))
        else:
            _current_packet_id = 0
            log("comm", "Starting fresh packet counter: 0")
        
        # Initialize device discovery
        log("comm", "═══════════════════════════════════════════════")
        log("comm", "Starting UDP beacon discovery for ESP32-B...")
        log("comm", "Broadcasting on port {}".format(37020))
        _device_discovery = DeviceDiscovery(is_device_b=False)
        
        _initialized = True
        log("comm", "Communication initialized - auto-discovery enabled")
        log("comm", "No hardcoded IP needed! Discovering ESP32-B via UDP beacon...")
        log("comm", "═══════════════════════════════════════════════")
        return True
        
    except Exception as e:
        log("comm", "Init failed: {}".format(e))
        return False


# ===========================
# DATA SENDING
# ===========================

def send_data(payload):
    """Send JSON payload to ESP32-B with automatic packet tracking.
    
    Args:
        payload: Dictionary with data to send (will add packet_id automatically)
        
    Returns:
        True if successful, False otherwise
    """
    global _device_discovery, _current_packet_id
    
    # Check if we have discovered B's IP
    if not _device_discovery or not _device_discovery.get_other_ip():
        # Still discovering - not an error, just return
        return False
    
    try:
        # Add packet ID and device verification to payload
        payload["packet_id"] = _current_packet_id
        payload["device_key"] = get_device_key(is_device_b=False)
        payload["timestamp"] = time.time()
        
        # Build URL dynamically from discovered IP
        url = "http://{}:80/command".format(_device_discovery.get_other_ip())
        
        # Build JSON
        json_data = json.dumps(payload)
        
        # Send POST request
        response = urequests.post(
            url,
            data=json_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            # Mark as connected
            if _device_discovery:
                _device_discovery.mark_connected()
            
            # Increment packet ID and persist to state
            _current_packet_id += 1
            state.last_packet_id_sent_to_b = _current_packet_id
            
            log("comm", "TX packet #{}: sent successfully".format(_current_packet_id - 1))
            response.close()
            return True
        else:
            # Mark as disconnected, will trigger retry
            if _device_discovery:
                _device_discovery.mark_disconnected()
            log("comm", "Send failed: HTTP {}".format(response.status_code))
            response.close()
            return False
            
    except Exception as e:
        # Mark as disconnected on any error
        if _device_discovery:
            _device_discovery.mark_disconnected()
        log("comm", "Send error: {} - retrying...".format(e))
        return False


# ===========================
# UPDATE LOOP
# ===========================

def update():
    """Update communication system (discovery, connection monitoring).
    
    Called from main loop. Uses elapsed() for non-blocking timing.
    Handles beacon sending/receiving for auto-discovery.
    """
    global _device_discovery
    
    if not _initialized:
        return
    
    # Update discovery/retry logic (beacon listening + sending)
    if _device_discovery:
        _device_discovery.update_discovery()


# ===========================
# STATUS QUERIES
# ===========================

def is_connected():
    """Check if ESP32-B is reachable and connection is established."""
    global _device_discovery
    
    if not _initialized or not _device_discovery:
        return False
    
    return _device_discovery.is_connected() and _device_discovery.get_other_ip() is not None


def get_discovered_ip():
    """Get the discovered IP address of ESP32-B.
    
    Returns:
        IP address string or None if not discovered yet
    """
    global _device_discovery
    
    if not _initialized or not _device_discovery:
        return None
    
    return _device_discovery.get_other_ip()


def get_packet_id():
    """Get current packet ID counter.
    
    Returns:
        Current packet ID (next packet to be sent will have this ID)
    """
    return _current_packet_id
