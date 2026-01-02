"""Low-level communication management for ESP32-B (ESP-NOW only).

Handles:
- ESP-NOW reception of commands from ESP32-A
- Packet tracking and validation
- Connection status monitoring (set true when a packet is received)

Does NOT handle command execution - that's in command_handler.py
"""

import json
import network  # type: ignore
import espnow   # type: ignore
from debug.debug import log
from core import state
from comms.device_id import get_device_key
from config.config import MAC_A_BYTES

# ===========================
# MODULE STATE
# ===========================

_initialized = False
_connected = False  # updated when packets arrive

# ESPNOW transport
_esp = None
_wlan = None

# Packet tracking (detects missing packets from A)
_last_received_packet_id = -1
_expected_next_id = 0

# Command callback (set by command_handler)
_command_callback = None


# ===========================
# INITIALIZATION
# ===========================

def init_communication():
    """Initialize communication system in ESP-NOW mode.
    
    Loads last received packet ID from persistent state.
    Returns True on success, False otherwise.
    """
    global _initialized, _connected, _esp, _wlan
    global _last_received_packet_id, _expected_next_id
    try:
        # Restore packet tracking if available
        if hasattr(state, "last_packet_id_from_a") and state.last_packet_id_from_a >= 0:
            _last_received_packet_id = state.last_packet_id_from_a
            _expected_next_id = _last_received_packet_id + 1
            log("comm", "Resumed packet tracking: expecting packet #{}".format(_expected_next_id))
        else:
            log("comm", "Starting fresh packet tracking from 0")

        # ESP-NOW receiver setup
        _wlan = network.WLAN(network.STA_IF)
        _wlan.active(True)
        _esp = espnow.ESPNow()
        _esp.active(True)
        _esp.add_peer(MAC_A_BYTES)
        log("comm", "ESP-NOW enabled (peer A added)")

        _initialized = True
        _connected = False
        log("comm", "ESP-NOW reception active")
        return True
    except Exception as e:
        log("comm", "Init failed: {}".format(e))
        _esp = None
        _initialized = False
        return False


# ===========================
# COMMAND CALLBACK REGISTRATION
# ===========================

def register_command_callback(callback):
    """Register callback function to handle received commands."""
    global _command_callback
    _command_callback = callback
    log("comm", "Command callback registered")


# ===========================
# PACKET VALIDATION
# ===========================

def _validate_packet(payload):
    """Validate received packet structure and sequence ID."""
    global _last_received_packet_id, _expected_next_id

    device_key = payload.get("device_key")
    if device_key != get_device_key(is_device_b=False):
        log("comm", "ERROR: Invalid device key: {}".format(device_key))
        return False

    packet_id = payload.get("packet_id")
    if packet_id is None:
        log("comm", "ERROR: Packet missing ID field")
        return False

    if _last_received_packet_id >= 0:
        expected_id = _last_received_packet_id + 1
        if packet_id != expected_id:
            if packet_id > expected_id:
                missing_count = packet_id - expected_id
                log("comm", "ERROR: Missing {} packet(s)! Expected {}, got {}".format(
                    missing_count, expected_id, packet_id
                ))
            else:
                log("comm", "WARNING: Received old packet ID {} (expected {})".format(
                    packet_id, expected_id
                ))

    _last_received_packet_id = packet_id
    _expected_next_id = packet_id + 1
    state.last_packet_id_from_a = packet_id
    return True


# ===========================
# ESPNOW HANDLING
# ===========================

def _handle_espnow_message(mac, msg):
    """Handle ESP-NOW incoming message (JSON payload)."""
    global _connected
    try:
        payload = json.loads(msg.decode("utf-8"))
        if not _validate_packet(payload):
            return

        packet_id = payload.get("packet_id")
        command = payload.get("command")
        params = payload.get("params", {})

        log("comm", "┌─────────────────────────────────────────────")
        log("comm", "│ ✓ Received packet #{} from ESP32-A (ESP-NOW)".format(packet_id))
        log("comm", "│ Command: '{}'".format(command))
        log("comm", "│ Params: {}".format(params))
        log("comm", "└─────────────────────────────────────────────")

        if _command_callback:
            _command_callback(command, params)
        else:
            log("comm", "WARNING: No command callback registered!")

        _connected = True
    except Exception as e:
        log("comm", "ESP-NOW handling error: {}".format(e))


# ===========================
# UPDATE LOOP
# ===========================

def update():
    """Update communication system (ESP-NOW only)."""
    global _esp

    if not _initialized:
        return

    if _esp:
        try:
            mac, msg = _esp.recv(0)  # non-blocking
            if mac is not None and msg:
                _handle_espnow_message(mac, msg)
        except OSError:
            pass
        except Exception as e:
            log("comm", "ESP-NOW recv error: {}".format(e))


# ===========================
# STATUS QUERIES
# ===========================

def is_connected():
    """Check if ESP32-A is reachable and connection is established."""
    global _connected

    if not _initialized:
        return False
    return _connected
