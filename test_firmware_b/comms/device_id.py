"""
Device identification and auto-discovery module.

Handles:
- Automatic discovery via UDP broadcast beacon
- No hardcoded IP or MAC addresses needed
- Plug-and-play communication setup
"""

import socket
import json
import time
import network  # type: ignore
from debug.debug import log
from core.timers import elapsed

# Device identity keys (immutable)
DEVICE_KEY_B = "ESP32B_ACTUATORS_v1"
DEVICE_KEY_A = "ESP32A_SENSORS_v1"

# UDP beacon configuration
BEACON_PORT = 37020  # Custom port for discovery
BEACON_INTERVAL_MS = 5000  # Send beacon every 5 seconds
DISCOVERY_TIMEOUT_MS = 30000  # Give up after 30 seconds


def get_own_ip():
    """Get IP address of this device from WiFi interface."""
    try:
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            ip = wlan.ifconfig()[0]
            return ip
        return None
    except Exception as e:
        log("device_id", "Failed to get IP: {}".format(e))
        return None


def get_device_key(is_device_b=True):
    """Get device identity key.
    
    Args:
        is_device_b: True if this is ESP32-B (actuators), False if A (sensors)
        
    Returns:
        Device identity key string
    """
    return DEVICE_KEY_B if is_device_b else DEVICE_KEY_A


def verify_device_key(received_key, is_device_b=True):
    """Verify that received key matches expected device.
    
    Args:
        received_key: Key received from other device
        is_device_b: True if this is B (expecting key from A)
        
    Returns:
        True if key is valid, False otherwise
    """
    if is_device_b:
        # B receives from A
        expected = DEVICE_KEY_A
    else:
        # A receives from B
        expected = DEVICE_KEY_B
    
    return received_key == expected


class DeviceDiscovery:
    """Handles automatic UDP beacon-based discovery."""
    
    def __init__(self, is_device_b=True):
        """Initialize discovery handler.
        
        Args:
            is_device_b: True if this is ESP32-B, False if A
        """
        self.is_device_b = is_device_b
        self.other_ip = None
        self.connection_established = False
        self.discovery_start_time = 0
        self.own_ip = None
        
        # UDP socket for beacons
        self.beacon_socket = None
        
        # Initialize beacon socket
        self._init_beacon_socket()
    
    def _init_beacon_socket(self):
        """Initialize UDP socket for beacon broadcasting/listening."""
        try:
            self.beacon_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.beacon_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.beacon_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.beacon_socket.setblocking(False)  # Non-blocking mode
            
            # Bind to beacon port for receiving
            self.beacon_socket.bind(('', BEACON_PORT))
            
            log("device_id", "Beacon socket initialized on port {}".format(BEACON_PORT))
        except Exception as e:
            log("device_id", "Beacon socket init failed: {}".format(e))
            self.beacon_socket = None

    def _compute_broadcast_ip(self):
        """Compute broadcast IP from current interface.

        Some firmwares reject 255.255.255.255; computing the interface broadcast
        avoids 'invalid arguments' send errors when WiFi is up.
        """
        try:
            wlan = network.WLAN(network.STA_IF)
            if not wlan.isconnected():
                return None

            ip, _, netmask, _ = wlan.ifconfig()
            ip_parts = [int(part) for part in ip.split('.')]
            mask_parts = [int(part) for part in netmask.split('.')]

            broadcast_parts = [
                ip_parts[i] | (~mask_parts[i] & 0xFF) for i in range(4)
            ]
            return "{}.{}.{}.{}".format(*broadcast_parts)
        except Exception:
            # Fallback to global broadcast if computation fails
            return "255.255.255.255"
    
    def _send_beacon(self):
        """Send UDP beacon announcing this device."""
        if not self.beacon_socket:
            return
        
        try:
            # Get own IP
            self.own_ip = get_own_ip()
            if not self.own_ip:
                return

            # Pick a broadcast address that matches the current network
            broadcast_ip = self._compute_broadcast_ip()
            if not broadcast_ip:
                return
            
            # Create beacon payload
            beacon = {
                "type": "beacon",
                "device": "B" if self.is_device_b else "A",
                "device_key": get_device_key(self.is_device_b),
                "ip": self.own_ip,
                "timestamp": time.time()
            }
            
            # Broadcast
            message = json.dumps(beacon).encode('utf-8')
            self.beacon_socket.sendto(message, (broadcast_ip, BEACON_PORT))
            
        except Exception as e:
            log("device_id", "Beacon send failed: {}".format(e))
    
    def _listen_for_beacons(self):
        """Listen for beacons from other device."""
        if not self.beacon_socket:
            return
        
        try:
            data, addr = self.beacon_socket.recvfrom(1024)
            
            # Parse beacon
            beacon = json.loads(data.decode('utf-8'))
            
            # Check if this is from the other device
            expected_device = "A" if self.is_device_b else "B"
            if beacon.get("device") != expected_device:
                return  # Not the device we're looking for
            
            # Verify device key
            expected_key = DEVICE_KEY_A if self.is_device_b else DEVICE_KEY_B
            if beacon.get("device_key") != expected_key:
                log("device_id", "Invalid device key in beacon")
                return
            
            # Extract IP
            other_ip = beacon.get("ip")
            if other_ip:
                if self.other_ip != other_ip:
                    log("device_id", "═══════════════════════════════════════════════")
                    log("device_id", "✓ DISCOVERED ESP32-{} at {}".format(
                        expected_device, other_ip
                    ))
                    log("device_id", "✓ Device key verified: {}".format(expected_key[:20] + "..."))
                    log("device_id", "✓ Connection established successfully!")
                    log("device_id", "═══════════════════════════════════════════════")
                self.other_ip = other_ip
                self.connection_established = True
                self.discovery_start_time = 0  # Reset timer
            
        except OSError:
            pass  # No beacon received (expected in non-blocking mode)
        except Exception as e:
            log("device_id", "Beacon listen error: {}".format(e))
    
    def update_discovery(self, force=False):
        """Non-blocking discovery update.
        
        Uses UDP beacons for automatic discovery.
        
        Args:
            force: If True, send beacon immediately
        """
        # Send beacon periodically
        if force or elapsed("device_beacon", BEACON_INTERVAL_MS):
            self._send_beacon()
        
        # Listen for beacons from other device
        self._listen_for_beacons()
        
        # Check timeout
        if not self.connection_established:
            if self.discovery_start_time == 0:
                self.discovery_start_time = time.time()
            elif time.time() - self.discovery_start_time > (DISCOVERY_TIMEOUT_MS / 1000):
                log("device_id", "Discovery timeout - will continue trying")
                self.discovery_start_time = 0
    
    def get_other_ip(self):
        """Get discovered IP address of other device."""
        return self.other_ip
    
    def mark_connected(self):
        """Mark that connection with other device is established."""
        self.connection_established = True
        self.discovery_start_time = 0
    
    def mark_disconnected(self):
        """Mark that connection with other device is lost."""
        self.connection_established = False
        # Don't reset other_ip - we'll try to reconnect to same IP
        log("device_id", "Connection lost - will retry discovery")
    
    def is_connected(self):
        """Check if other device is connected."""
        return self.connection_established and self.other_ip is not None
