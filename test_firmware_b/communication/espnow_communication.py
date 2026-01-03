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
import network  # type: ignore
from debug.debug import log

# MAC addresses
MAC_B = bytes.fromhex("5C013B4C2C34")  # Self (B)
MAC_A = bytes.fromhex("5C013B875310")  # Remote (A)

_esp_now = None
_initialized = False
_wifi = None


def init_espnow_comm():
    """Initialize ESP-NOW on Scheda B (Server mode).
    
    Server waits for connections from Scheda A (client).
    """
    global _esp_now, _initialized, _wifi
    try:
        # Get WiFi interface in station mode for ESP-NOW
        _wifi = network.WLAN(network.STA_IF)
        _wifi.active(True)
        
        # Initialize ESP-NOW
        _esp_now = espnow.ESPNow()
        _esp_now.active(True)
        
        # Add Scheda A as a peer (client will connect to this)
        _esp_now.add_peer(MAC_A)
        
        _initialized = True
        
        # Get actual MAC address
        actual_mac = _wifi.config('mac')
        mac_str = ":".join("{:02X}".format(b) for b in actual_mac)
        
        log("espnow_b", "ESP-NOW initialized (Server mode)")
        log("espnow_b", "My MAC: {}".format(mac_str))
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
    
    Returns:
        True if sent successfully, False otherwise
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
        mac, msg = _esp_now.irecv(0)
        if mac is not None and msg is not None:
            # Process received message
            mac_str = ":".join("{:02X}".format(b) for b in mac)
            try:
                msg_str = msg.decode("utf-8")
                log("espnow_b", "RX from {}: {}".format(mac_str, msg_str))
            except:
                log("espnow_b", "RX from {}: {} bytes".format(mac_str, len(msg)))
    except Exception as e:
        log("espnow_b", "Update error: {}".format(e))
