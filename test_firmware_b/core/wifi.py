"""WiFi connection management for ESP32-B.

Imported by: main.py
Imports: time, network, debug.debug, config.wifi_config

Handles WiFi initialization and connection verification.
Blocking during init phase (15s timeout), then fully connected.

Used for:
- Remote UDP logging to development PC
- OTA updates via GitHub
- Future MQTT integration (if needed)

WiFi credentials loaded from config.wifi_config (WIFI_SSID, WIFI_PASSWORD).
Board B doesn't require WiFi for core operation (ESP-NOW works without it),
but WiFi enables development/monitoring features.
"""

from time import time, sleep  # type: ignore
import network  # type: ignore
from debug.debug import log
from config.wifi_config import WIFI_SSID, WIFI_PASSWORD

_wlan = None
_initialized = False


def init_wifi():
    """Initialize WiFi connection (blocking during init phase only)."""
    global _wlan, _initialized
    
    _wlan = network.WLAN(network.STA_IF)
    
    if _wlan.isconnected():
        log("core.wifi", "Already connected: {}".format(_wlan.ifconfig()[0]))
        _initialized = True
        return True
    
    log("core.wifi", "Connecting to {}...".format(WIFI_SSID))
    _wlan.active(True)
    _wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    
    # Blocking wait during init only
    timeout = 15
    start = time()
    while not _wlan.isconnected():
        if time() - start > timeout:
            log("core.wifi", "Connection timeout")
            _initialized = False
            return False
        sleep(0.2)
    
    log("core.wifi", "Connected: {}".format(_wlan.ifconfig()[0]))
    _initialized = True
    return True


def is_connected():
    """Check if WiFi is connected (non-blocking)."""
    if not _wlan:
        return False
    return _wlan.isconnected()


def get_ip():
    """Get current IP address."""
    if _wlan and _wlan.isconnected():
        return _wlan.ifconfig()[0]
    return None
