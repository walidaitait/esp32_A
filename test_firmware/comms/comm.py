"""Low-level communication management for ESP32-A (ESP-NOW only).

Handles:
- ESP-NOW transport to ESP32-B
- Packet tracking (sequence IDs)
- Connection status monitoring

Does NOT handle command logic - that's in command_sender.py
"""

import json
import time
import network  # type: ignore
import espnow   # type: ignore
from debug.debug import log
from core import state
from comms.device_id import get_device_key
from config.config import USE_ESPNOW, MAC_B_BYTES

# ===========================
# MODULE STATE
# ===========================

_initialized = False

# ESPNOW transport
_esp = None
_wlan = None
_connected = False  # for ESP-NOW path

# Packet tracking (persistent across reboots)
_current_packet_id = 0


# ===========================
# INITIALIZATION
# ===========================

def init_communication():
    """Initialize communication system (ESP-NOW only).
    
    Returns:
        True if initialization successful, False otherwise
    """
    global _initialized, _current_packet_id, _esp, _wlan, _connected
    
    try:
        # Load last packet ID from state (survives reboots)
        if hasattr(state, 'last_packet_id_sent_to_b') and state.last_packet_id_sent_to_b >= 0:
            _current_packet_id = state.last_packet_id_sent_to_b + 1
            log("comm", "Resumed packet counter from state: {}".format(_current_packet_id))
        else:
            _current_packet_id = 0
            log("comm", "Starting fresh packet counter: 0")
        
        # Initialize ESP-NOW transport
        log("comm", "═══════════════════════════════════════════════")
        _wlan = network.WLAN(network.STA_IF)
        _wlan.active(True)
        try:
            _esp = espnow.ESPNow()
            _esp.active(True)
            _esp.add_peer(MAC_B_BYTES)
            log("comm", "ESP-NOW enabled (peer B added)")
        except Exception as e:
            log("comm", "ESP-NOW init failed: {}".format(e))
            _esp = None
        
        _initialized = True
        log("comm", "Communication initialized - ESP-NOW transport active")
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
    
    # ESP-NOW path
    if USE_ESPNOW:
        if not _esp:
            return False

        try:
            # Add packet ID and device verification to payload
            payload["packet_id"] = _current_packet_id
            payload["device_key"] = get_device_key(is_device_b=False)
            payload["timestamp"] = time.time()

            json_data = json.dumps(payload)
            ok = _esp.send(MAC_B_BYTES, json_data)
            if ok:
                _connected = True
                _current_packet_id += 1
                state.last_packet_id_sent_to_b = _current_packet_id
                log("comm", "TX packet #{} (ESP-NOW): sent".format(_current_packet_id - 1))
                return True
            else:
                _connected = False
                log("comm", "Send failed (ESP-NOW)")
                return False
        except Exception as e:
            _connected = False
            log("comm", "Send error (ESP-NOW): {}".format(e))
            return False

    # HTTP path (discovery or static IP)
    if USE_STATIC_IP_B:
        dest_ip = B_STATIC_IP
    else:
        if not _device_discovery or not _device_discovery.get_other_ip():
            # Still discovering - not an error, just return
            return False
        dest_ip = _device_discovery.get_other_ip()
    
    try:
        # Add packet ID and device verification to payload
        payload["packet_id"] = _current_packet_id
        payload["device_key"] = get_device_key(is_device_b=False)
        payload["timestamp"] = time.time()
        
        # Build URL dynamically from chosen IP
        url = "http://{}:80/command".format(dest_ip)
        
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
            if not USE_STATIC_IP_B and _device_discovery:
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
    
    # ESP-NOW requires no periodic update
    return


# ===========================
# STATUS QUERIES
# ===========================

def is_connected():
    """Check if ESP32-B is reachable and connection is established."""
    global _connected
    
    if not _initialized:
        return False
    return _connected


def get_discovered_ip():
    """Get the discovered IP address of ESP32-B.
    
    Returns:
        IP address string or None if not discovered yet
    """
    global _device_discovery
    
    return None


def get_packet_id():
    """Get current packet ID counter.
    
    Returns:
        Current packet ID (next packet to be sent will have this ID)
    """
    return _current_packet_id
