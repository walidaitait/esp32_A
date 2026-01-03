"""ESP-NOW communication module for ESP32-B (Actuators - Server).

Scheda B (Server):
- Waits for incoming connections from Scheda A
- Receives messages and logs them
- Can send messages back to Scheda A once connected

MAC Addresses:
- Scheda B (self): 5C:01:3B:4C:2C:34
- Scheda A: 5C:01:3B:87:53:10
"""

import espnow  # type: ignore
from machine import WiFi  # type: ignore
from debug.debug import log

# MAC addresses
MAC_B = bytes.fromhex("5C:01:3B:4C:2C:34")  # Self (B)
MAC_A = bytes.fromhex("5C:01:3B:87:53:10")  # Remote (A)

_esp_now = None
_initialized = False
_peers = {}  # Track connected peers


def _on_recv(mac, msg):
    """Callback when message is received from peer."""
    try:
        mac_str = ":".join("{:02X}".format(b) for b in mac)
        msg_str = msg.decode("utf-8", errors="ignore")
        log("espnow_b", "Message from {}: {}".format(mac_str, msg_str))
    except Exception as e:
        log("espnow_b", "Recv error: {}".format(e))


def _on_sent(mac, status):
    """Callback when message is sent to peer."""
    try:
        mac_str = ":".join("{:02X}".format(b) for b in mac)
        status_str = "OK" if status == 0 else "FAIL"
        log("espnow_b", "Message sent to {}: {}".format(mac_str, status_str))
    except Exception as e:
        log("espnow_b", "Sent callback error: {}".format(e))


def init_espnow_comm():
    """Initialize ESP-NOW on Scheda B (Server mode).
    
    Server waits for connections from Scheda A (client).
    """
    global _esp_now, _initialized
    try:
        # Get WiFi interface
        wifi = WiFi.mode(WiFi.AP_STA)
        
        # Initialize ESP-NOW
        _esp_now = espnow.ESPNow()
        _esp_now.active(True)
        _esp_now.config(pmk=b"pmk1234567890ab")  # Shared PMK for all peers
        
        # Set MAC address for Scheda B
        wifi.config(mac=MAC_B)
        
        # Add Scheda A as a peer (client will connect to this)
        _esp_now.add_peer(MAC_A, channel=0, ifidx=0)
        _peers[MAC_A] = True
        
        # Register callbacks
        _esp_now.recv_cb(_on_recv)
        _esp_now.send_cb(_on_sent)
        
        _initialized = True
        log("espnow_b", "ESP-NOW initialized (Server mode)")
        log("espnow_b", "Waiting for messages from Scheda A ({})".format(
            ":".join("{:02X}".format(b) for b in MAC_A)
        ))
        return True
    except Exception as e:
        log("espnow_b", "Initialization failed: {}".format(e))
        _esp_now = None
        _initialized = False
        return False


def send_message(data):
    """Send message to Scheda A.
    
    Args:
        data: String or bytes to send
    """
    if not _initialized or _esp_now is None:
        log("espnow_b", "ESP-NOW not initialized")
        return False
    
    try:
        if isinstance(data, str):
            data = data.encode("utf-8")
        
        _esp_now.send(MAC_A, data)
        return True
    except Exception as e:
        log("espnow_b", "Send error: {}".format(e))
        return False


def update():
    """Non-blocking update for ESP-NOW communication.
    
    Called periodically from main loop to check for incoming messages.
    """
    if not _initialized or _esp_now is None:
        return
    
    try:
        # Check for new messages (non-blocking with timeout=0)
        host, msg = _esp_now.irecv(0)
        if host is not None:
            # Message received (handled by callback)
            pass
    except Exception as e:
        log("espnow_b", "Update error: {}".format(e))
