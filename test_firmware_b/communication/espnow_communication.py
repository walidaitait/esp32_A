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
from time import ticks_ms, ticks_diff  # type: ignore
from debug.debug import log
from core import state
from core.timers import elapsed
from config import config
try:
    import ujson as json  # type: ignore  # MicroPython
except ImportError:
    import json  # Fallback

# MAC addresses
MAC_B = bytes.fromhex("5C013B4C2C34")  # Self (B)
MAC_A = bytes.fromhex("5C013B875310")  # Remote (A)

# Heartbeat and connection tracking
HEARTBEAT_INTERVAL = 10000  # Send heartbeat every 10 seconds
CONNECTION_TIMEOUT = 20000  # Consider A disconnected if no message for 20 seconds
REINIT_INTERVAL = 5000      # Try to recover ESP-NOW every 5 seconds when down
_last_message_from_a = 0
_a_is_connected = False
_version_mismatch_logged = False  # Prevent log spam
_messages_received = 0
_state_log_interval = None  # Disabled snapshots

_esp_now = None
_initialized = False
_wifi = None
_last_init_attempt = 0


def _get_actuator_status_string():
    """Format all actuator states into a JSON message."""
    modes = state.actuator_state["led_modes"]
    data = {
        "version": config.FIRMWARE_VERSION,
        "type": "actuators",
        "timestamp": ticks_ms(),
        "leds": {
            "green": modes.get("green", "off"),
            "blue": modes.get("blue", "off"),
            "red": modes.get("red", "off"),
        },
        "servo": {
            "angle": state.actuator_state["servo"].get("angle"),
        },
        "lcd": {
            "line1": state.actuator_state["lcd"].get("line1", "")[:16],
            "line2": state.actuator_state["lcd"].get("line2", "")[:16],
        },
        "buzzer": "ON" if state.actuator_state["buzzer"].get("active", False) else "OFF",
        "audio": "PLAY" if state.actuator_state["audio"].get("playing", False) else "STOP",
        "sos_active": state.actuator_state.get("sos_mode", False),
    }
    return json.dumps(data).encode("utf-8")


def init_espnow_comm():
    """Initialize ESP-NOW on Scheda B (Server mode).
    
    Server waits for connections from Scheda A (client).
    """
    global _esp_now, _initialized, _wifi, _last_init_attempt
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
        _last_init_attempt = ticks_ms()
        
        # Get actual MAC address
        try:
            actual_mac = _wifi.config('mac')
        except (AttributeError, OSError):
            actual_mac = MAC_B  # Fallback to configured MAC
        mac_str = ":".join("{:02X}".format(b) for b in actual_mac)
        
        log("communication.espnow", "ESP-NOW initialized (Server mode)")
        log("communication.espnow", "My MAC: {}".format(mac_str))
        log("communication.espnow", "Peer added: Scheda A ({})".format(
            ":".join("{:02X}".format(b) for b in MAC_A)
        ))
        log("communication.espnow", "Ready to receive messages")
        return True
    except Exception as e:
        log("communication.espnow", "Initialization failed: {}".format(e))
        _esp_now = None
        _initialized = False
        _last_init_attempt = ticks_ms()
        return False


def send_message(data):
    """Send message to Scheda A.
    
    Args:
        data: String or bytes to send
    
    Returns:
        True if sent successfully, False otherwise
    """
    global _initialized, _esp_now
    if not _initialized or _esp_now is None:
        log("communication.espnow", "ESP-NOW not initialized")
        return False
    
    try:
        if isinstance(data, str):
            data = data.encode("utf-8")
        
        # Debug: show outgoing payload size and preview
        preview = data[:40]
        log("espnow_b", "TX -> A len={} preview={}".format(len(data), preview))
        
        _esp_now.send(MAC_A, data)
        log("espnow_b", "TX OK to A")
        return True
    except Exception as e:
        log("communication.espnow", "Send error: {}".format(e))
        # Force a re-init on next update
        _initialized = False
        _esp_now = None
        return False


def _parse_sensor_state(msg_bytes):
    """Parse received sensor state from Board A (JSON format) and update state.
    
    Expected JSON format:
    {
        "version": 1,
        "type": "sensors",
        "timestamp": 12345678,
        "sensors": {
            "temperature": 23.5,
            "co": 150,
            "heart_rate": {"bpm": 75, "spo2": 98},
            "ultrasonic_distance": 45,
            "presence_detected": false
        },
        "buttons": {"b1": false, "b2": true, "b3": false},
        "alarm": {"level": "normal", "source": null}
    }
    """
    try:
        msg_str = msg_bytes.decode("utf-8")
        log("espnow_b", "RX Parse: msg_str={}".format(msg_str[:100]))
        data = json.loads(msg_str)
        
        # Check version (warning only, don't block communication)
        remote_version = data.get("version")
        if remote_version != config.FIRMWARE_VERSION:
            global _version_mismatch_logged
            if not _version_mismatch_logged:
                log("communication.espnow", "WARNING: Firmware version mismatch! Local=v{}, Remote=v{}".format(
                    config.FIRMWARE_VERSION, remote_version
                ))
                _version_mismatch_logged = True
        else:
            _version_mismatch_logged = False
        
        # Parse sensors
        sensors = data.get("sensors", {})
        state.received_sensor_state["temperature"] = sensors.get("temperature")
        state.received_sensor_state["co"] = sensors.get("co")
        state.received_sensor_state["ultrasonic_distance"] = sensors.get("ultrasonic_distance")
        state.received_sensor_state["presence_detected"] = sensors.get("presence_detected", False)
        
        # Parse heart rate
        hr = sensors.get("heart_rate", {})
        state.received_sensor_state["heart_rate_bpm"] = hr.get("bpm")
        state.received_sensor_state["heart_rate_spo2"] = hr.get("spo2")
        
        # Parse buttons
        buttons = data.get("buttons", {})
        state.received_sensor_state["button_b1"] = buttons.get("b1", False)
        state.received_sensor_state["button_b2"] = buttons.get("b2", False)
        state.received_sensor_state["button_b3"] = buttons.get("b3", False)
        
        # Parse alarm
        alarm = data.get("alarm", {})
        state.received_sensor_state["alarm_level"] = alarm.get("level", "normal")
        state.received_sensor_state["alarm_source"] = alarm.get("source")
        state.received_sensor_state["last_update"] = ticks_ms()
        state.received_sensor_state["is_stale"] = False
        
        log("communication.espnow", "Sensor data received (v{}) - Temp={}, CO={}, Alarm={}".format(
            remote_version,
            sensors.get("temperature"),
            sensors.get("co"),
            alarm.get("level")
        ))
        log("espnow_b", "RX OK - Sensor state updated")
    except Exception as e:
        log("communication.espnow", "Parse error: {}".format(e))
        log("espnow_b", "RX Parse FAILED: {}".format(e))


def _log_complete_state():
    """Log complete state including local actuators and received sensors."""
    log("communication.espnow", "=" * 60)
    log("communication.espnow", "COMPLETE STATE SNAPSHOT (Board B)")
    log("communication.espnow", "=" * 60)
    
    # Local actuator data (sent to A)
    modes = state.actuator_state["led_modes"]
    log("communication.espnow", "LOCAL ACTUATORS (sent to A):")
    log("communication.espnow", "  LEDs: Green={}, Blue={}, Red={}".format(
        modes.get("green", "off"), modes.get("blue", "off"), modes.get("red", "off")
    ))
    log("communication.espnow", "  Servo: {}°".format(
        state.actuator_state["servo"].get("angle", "N/A")
    ))
    log("communication.espnow", "  LCD: '{}' / '{}'".format(
        state.actuator_state["lcd"].get("line1", ""),
        state.actuator_state["lcd"].get("line2", "")
    ))
    log("communication.espnow", "  Buzzer: {}, Audio: {}".format(
        "ON" if state.actuator_state["buzzer"].get("active", False) else "OFF",
        "PLAY" if state.actuator_state["audio"].get("playing", False) else "STOP"
    ))
    
    # Received sensor data from A
    log("communication.espnow", "")
    log("communication.espnow", "RECEIVED SENSORS (from A):")
    recv = state.received_sensor_state
    log("communication.espnow", "  Temperature: {}°C".format(recv["temperature"] if recv["temperature"] is not None else "N/A"))
    log("communication.espnow", "  CO: {} ppm".format(recv["co"] if recv["co"] is not None else "N/A"))
    log("communication.espnow", "  Heart Rate: {} bpm, SpO2: {}%".format(
        recv["heart_rate_bpm"] if recv["heart_rate_bpm"] is not None else "N/A",
        recv["heart_rate_spo2"] if recv["heart_rate_spo2"] is not None else "N/A"
    ))
    log("communication.espnow", "  Ultrasonic: {} cm".format(
        recv["ultrasonic_distance"] if recv["ultrasonic_distance"] is not None else "N/A"
    ))
    log("communication.espnow", "  Buttons: B1={}, B2={}, B3={}".format(
        recv["button_b1"], recv["button_b2"], recv["button_b3"]
    ))
    log("communication.espnow", "=" * 60)


def _parse_sensor_state_v0_fallback(msg_str):
    """Fallback parser for old string format (for backward compatibility).
    
    Old format: "V:1 SENSORS: Temp=23.5 CO=150 HR=75 SpO2=98 Dist=45 Btns=False|True|False"
    """
    try:
        if "Temp=" in msg_str:
            temp_str = msg_str.split("Temp=")[1].split()[0].strip()
            try:
                state.received_sensor_state["temperature"] = float(temp_str) if temp_str != "N/A" else None
            except:
                state.received_sensor_state["temperature"] = None
        
        if "CO=" in msg_str:
            co_str = msg_str.split("CO=")[1].split()[0].strip()
            try:
                state.received_sensor_state["co"] = float(co_str) if co_str != "N/A" else None
            except:
                state.received_sensor_state["co"] = None
        
        if "HR=" in msg_str:
            hr_str = msg_str.split("HR=")[1].split()[0].strip()
            try:
                state.received_sensor_state["heart_rate_bpm"] = int(hr_str) if hr_str != "N/A" else None
            except:
                state.received_sensor_state["heart_rate_bpm"] = None
        
        if "SpO2=" in msg_str:
            spo2_str = msg_str.split("SpO2=")[1].split()[0].strip()
            try:
                state.received_sensor_state["heart_rate_spo2"] = int(spo2_str) if spo2_str != "N/A" else None
            except:
                state.received_sensor_state["heart_rate_spo2"] = None
        
        if "Dist=" in msg_str:
            dist_str = msg_str.split("Dist=")[1].split()[0].strip()
            try:
                state.received_sensor_state["ultrasonic_distance"] = float(dist_str) if dist_str != "N/A" else None
            except:
                state.received_sensor_state["ultrasonic_distance"] = None

        if "Presence=" in msg_str:
            pres_str = msg_str.split("Presence=")[1].split()[0].strip()
            state.received_sensor_state["presence_detected"] = (pres_str.lower() == "true")

        if "Alarm=" in msg_str:
            alarm_str = msg_str.split("Alarm=")[1].split()[0].strip()
            if ":" in alarm_str:
                level_part, source_part = alarm_str.split(":", 1)
                state.received_sensor_state["alarm_level"] = level_part
                state.received_sensor_state["alarm_source"] = source_part
            else:
                state.received_sensor_state["alarm_level"] = alarm_str
                state.received_sensor_state["alarm_source"] = None
        
        if "Btns=" in msg_str:
            btns_str = msg_str.split("Btns=")[1].strip()
            btns = btns_str.split("|")
            if len(btns) >= 3:
                state.received_sensor_state["button_b1"] = (btns[0].strip().lower() == "true")
                state.received_sensor_state["button_b2"] = (btns[1].strip().lower() == "true")
                state.received_sensor_state["button_b3"] = (btns[2].strip().lower() == "true")
        
        state.received_sensor_state["last_update"] = ticks_ms()
        state.received_sensor_state["is_stale"] = False
        log("communication.espnow", "Parsed with v0 fallback format")
    except Exception as e:
        log("communication.espnow", "Fallback parse error: {}".format(e))


def update():
    """Non-blocking update for ESP-NOW communication.
    
    Called periodically from main loop to receive sensor data from A
    and respond with actuator status.
    """
    global _messages_received, _last_message_from_a, _a_is_connected
    
    if not _initialized or _esp_now is None:
        # Auto-recover ESP-NOW if it went down
        if elapsed("espnow_reinit", REINIT_INTERVAL):
            log("communication.espnow", "ESP-NOW down, attempting re-init")
            init_espnow_comm()
        return
    
    try:
        # Check if A is still connected (heartbeat timeout check)
        now = ticks_ms()
        if _last_message_from_a > 0:
            elapsed_since = ticks_diff(now, _last_message_from_a)
            if elapsed_since > CONNECTION_TIMEOUT:
                if _a_is_connected:
                    log("communication.espnow", "WARNING: Board A disconnected (no message for 20s)")
                    _a_is_connected = False
                    # Inform actuator loop (updates LED state)
                    try:
                        from core import actuator_loop
                        actuator_loop.set_espnow_connected(False)
                    except Exception:
                        pass
                    # In standby mode, reset sensor state to safe defaults
                    state.received_sensor_state["alarm_level"] = "normal"
                    state.received_sensor_state["alarm_source"] = None
                    state.received_sensor_state["presence_detected"] = False
            else:
                if not _a_is_connected:
                    log("communication.espnow", "Board A reconnected")
                    _a_is_connected = True
        
        # Check for sensor data from A
        try:
            mac, msg = _esp_now.irecv(0)
        except OSError as e:
            # Buffer error or no data - this is normal, just skip
            mac, msg = None, None
        
        if mac is not None and msg is not None:
            try:
                mac_str = ":".join("{:02X}".format(b) for b in mac)
            except Exception:
                mac_str = str(mac)
            log("espnow_b", "RX from {} len={} preview={}".format(mac_str, len(msg), msg[:40]))
            try:
                # Parse JSON sensor data from A
                _parse_sensor_state(msg)
                _last_message_from_a = ticks_ms()
                if not _a_is_connected:
                    log("communication.espnow", "Board A connected")
                    _a_is_connected = True
                # Inform actuator loop (updates LED state)
                try:
                    from core import actuator_loop
                    actuator_loop.set_espnow_connected(True)
                except Exception:
                    pass
                
                # Send actuator status as response (bytes)
                _messages_received += 1
                actuator_status_bytes = _get_actuator_status_string()
                send_message(actuator_status_bytes)
            except:
                pass
        
        # Send periodic heartbeat to keep connection alive
        if elapsed("espnow_heartbeat", HEARTBEAT_INTERVAL):
            heartbeat = {
                "version": config.FIRMWARE_VERSION,
                "type": "heartbeat",
                "timestamp": ticks_ms()
            }
            send_message(json.dumps(heartbeat).encode("utf-8"))
        
        # Log complete state every 15 seconds
        if _state_log_interval and elapsed("espnow_state_log", _state_log_interval):
            _log_complete_state()
    except Exception as e:
        log("communication.espnow", "Update error: {}".format(e))
