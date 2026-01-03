"""ESP-NOW communication module for ESP32-A (Sensors - Client).

Scheda A (Client):
- Initiates connection to Scheda B (server)
- Sends messages to Scheda B
- Receives acknowledgments/responses from Scheda B

MAC Addresses:
- Scheda A (self): 5C:01:3B:87:53:10
- Scheda B: 5C:01:3B:4C:2C:34
"""

import espnow  # type: ignore
from machine import WiFi  # type: ignore
from time import ticks_ms, ticks_diff  # type: ignore
from debug.debug import log

# MAC addresses
MAC_A = bytes.fromhex("5C:01:3B:87:53:10")  # Self (A)
MAC_B = bytes.fromhex("5C:01:3B:4C:2C:34")  # Remote (B)

_esp_now = None
_initialized = False
_peers = {}  # Track connected peers
_last_send_time = 0
_send_interval = 1000  # Minimum 1 second between sends to B


def _on_recv(mac, msg):
    """Callback when message is received from peer."""
    try:
        mac_str = ":".join("{:02X}".format(b) for b in mac)
        msg_str = msg.decode("utf-8", errors="ignore")
        log("espnow_a", "Message from {}: {}".format(mac_str, msg_str))
    except Exception as e:
        log("espnow_a", "Recv error: {}".format(e))


def _on_sent(mac, status):
    """Callback when message is sent to peer."""
    try:
        mac_str = ":".join("{:02X}".format(b) for b in mac)
        status_str = "OK" if status == 0 else "FAIL"
        log("espnow_a", "Message sent to {}: {}".format(mac_str, status_str))
    except Exception as e:
        log("espnow_a", "Sent callback error: {}".format(e))


def init_espnow_comm():
    """Initialize ESP-NOW on Scheda A (Client mode).
    
    Client seeks connection to Scheda B (server).
    """
    global _esp_now, _initialized
    try:
        # Get WiFi interface
        wifi = WiFi.mode(WiFi.AP_STA)
        
        # Initialize ESP-NOW
        _esp_now = espnow.ESPNow()
        _esp_now.active(True)
        _esp_now.config(pmk=b"pmk1234567890ab")  # Shared PMK for all peers
        
        # Set MAC address for Scheda A
        wifi.config(mac=MAC_A)
        
        # Add Scheda B as a peer
        _esp_now.add_peer(MAC_B, channel=0, ifidx=0)
        _peers[MAC_B] = True
        
        # Register callbacks
        _esp_now.recv_cb(_on_recv)
        _esp_now.send_cb(_on_sent)
        
        _initialized = True
        log("espnow_a", "ESP-NOW initialized (Client mode)")
        log("espnow_a", "Connected to Scheda B ({})".format(
            ":".join("{:02X}".format(b) for b in MAC_B)
        ))
        return True
    except Exception as e:
        log("espnow_a", "Initialization failed: {}".format(e))
        _esp_now = None
        _initialized = False
        return False


def send_message(data):
    """Send message to Scheda B.
    
    Args:
        data: String or bytes to send
        
    Returns:
        True if message was sent, False otherwise
    """
    global _last_send_time
    
    if not _initialized or _esp_now is None:
        log("espnow_a", "ESP-NOW not initialized")
        return False
    
    try:
        if isinstance(data, str):
            data = data.encode("utf-8")
        
        _esp_now.send(MAC_B, data)
        _last_send_time = ticks_ms()
        return True
    except Exception as e:
        log("espnow_a", "Send error: {}".format(e))
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
        log("espnow_a", "Update error: {}".format(e))
