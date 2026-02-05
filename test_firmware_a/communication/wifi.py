"""WiFi connection management module for ESP32.

Imported by: main.py (Board A), main.py (Board B), ota_update.py
Imports: network (MicroPython), time (MicroPython), debug.debug, config.wifi_config

Provides WiFi station mode initialization and connection health monitoring.
Used for:
- UDP logging (remote debug messages)
- MQTT/Node-RED communication (Board A only)
- ESP-NOW (requires WiFi active but not necessarily connected)
- OTA updates (requires internet connection)

Note: WiFi initialization is blocking during startup phase only.
Once connected, all operations are non-blocking.
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
