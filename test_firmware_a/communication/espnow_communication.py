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
import network  # type: ignore
from time import ticks_ms, ticks_diff  # type: ignore
from debug.debug import log

# MAC addresses
MAC_A = bytes.fromhex("5C013B875310")  # Self (A)
MAC_B = bytes.fromhex("5C013B4C2C34")  # Remote (B)

_esp_now = None
_initialized = False
_wifi = None
_last_send_time = 0
_send_interval = 1000  # Minimum 1 second between sends to B


def init_espnow_comm():
    """Initialize ESP-NOW on Scheda A (Client mode).
    
    Client seeks connection to Scheda B (server).
    """
    global _esp_now, _initialized, _wifi
    try:
        # Get WiFi interface in station mode for ESP-NOW
        _wifi = network.WLAN(network.STA_IF)
        _wifi.active(True)
        
        # Initialize ESP-NOW
        _esp_now = espnow.ESPNow()
        _esp_now.active(True)
        
        # Add Scheda B as a peer
        _esp_now.add_peer(MAC_B)
        
        _initialized = True
        
        # Get actual MAC address
        actual_mac = _wifi.config('mac')
        mac_str = ":".join("{:02X}".format(b) for b in actual_mac)
        
        log("espnow_a", "ESP-NOW initialized (Client mode)")
        log("espnow_a", "My MAC: {}".format(mac_str))
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
        mac, msg = _esp_now.irecv(0)
        if mac is not None and msg is not None:
            # Process received message
            mac_str = ":".join("{:02X}".format(b) for b in mac)
            try:
                msg_str = msg.decode("utf-8")
                log("espnow_a", "RX from {}: {}".format(mac_str, msg_str))
            except:
                log("espnow_a", "RX from {}: {} bytes".format(mac_str, len(msg)))
    except Exception as e:
        log("espnow_a", "Update error: {}".format(e))
