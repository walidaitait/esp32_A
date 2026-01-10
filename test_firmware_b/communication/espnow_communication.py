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
from time import ticks_ms  # type: ignore
from debug.debug import log
from core import state
from core.timers import elapsed
from config import config

# MAC addresses
MAC_B = bytes.fromhex("5C013B4C2C34")  # Self (B)
MAC_A = bytes.fromhex("5C013B875310")  # Remote (A)

_esp_now = None
_initialized = False
_wifi = None
_messages_received = 0
_state_log_interval = None  # Disabled snapshots
_version_mismatch_logged = False  # Prevent log spam


def _get_actuator_status_string():
    """Format all actuator states into a compact string."""
    modes = state.actuator_state["led_modes"]
    data = "V:{} ACTUATORS: LEDs=G:{},B:{},R:{} Servo={}° LCD1='{}' LCD2='{}' Buzz={} Audio={}".format(
        config.FIRMWARE_VERSION,
        modes.get("green", "off"),
        modes.get("blue", "off"),
        modes.get("red", "off"),
        state.actuator_state["servo"].get("angle", "N/A"),
        state.actuator_state["lcd"].get("line1", "")[:10],  # Limit to 10 chars
        state.actuator_state["lcd"].get("line2", "")[:10],
        "ON" if state.actuator_state["buzzer"].get("active", False) else "OFF",
        "PLAY" if state.actuator_state["audio"].get("playing", False) else "STOP"
    )
    return data


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
        try:
            actual_mac = _wifi.config('mac')
        except (AttributeError, OSError):
            actual_mac = MAC_B  # Fallback to configured MAC
        mac_str = ":".join("{:02X}".format(b) for b in actual_mac)
        
        log("espnow_b", "ESP-NOW initialized (Server mode)")
        log("espnow_b", "My MAC: {}".format(mac_str))
        log("espnow_b", "Peer added: Scheda A ({})".format(
            ":".join("{:02X}".format(b) for b in MAC_A)
        ))
        log("espnow_b", "Ready to receive messages")
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


def _parse_sensor_state(msg_str):
    """Parse received sensor state from Board A and update state.
    
    Expected format: "V:1 SENSORS: Temp=23.5 CO=150 HR=75 SpO2=98 Dist=45 Btns=False|True|False"
    """
    try:
        # Check version first
        if "V:" in msg_str:
            version_str = msg_str.split("V:")[1].split()[0].strip()
            try:
                remote_version = int(version_str)
                if remote_version != config.FIRMWARE_VERSION:
                    global _version_mismatch_logged
                    if not _version_mismatch_logged:
                        log("espnow_b", "ERROR: Firmware version mismatch! Local=v{}, Remote=v{}".format(
                            config.FIRMWARE_VERSION, remote_version
                        ))
                        _version_mismatch_logged = True
                    return  # Ignore message due to version mismatch
                else:
                    _version_mismatch_logged = False  # Reset flag when versions match
            except:
                pass
        
        # Simple parsing - extract key values
        if "Temp=" in msg_str:
            temp_str = msg_str.split("Temp=")[1].split()[0].strip()
            try:
                state.received_sensor_state["temperature"] = float(temp_str) if temp_str != "N/A" else None
            except:
                state.received_sensor_state["temperature"] = None
        
        if "CO=" in msg_str:
            co_str = msg_str.split("CO=")[1].split()[0].strip()
            try:
                state.received_sensor_state["co"] = int(co_str) if co_str != "N/A" else None
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
                state.received_sensor_state["ultrasonic_distance"] = int(dist_str) if dist_str != "N/A" else None
            except:
                state.received_sensor_state["ultrasonic_distance"] = None

        if "Presence=" in msg_str:
            pres_str = msg_str.split("Presence=")[1].split()[0].strip()
            state.received_sensor_state["presence_detected"] = (pres_str.lower() == "true")

        if "Alarm=" in msg_str:
            alarm_str = msg_str.split("Alarm=")[1].split()[0].strip()
            # Expect format level:source
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
    except Exception as e:
        log("espnow_b", "Parse error: {}".format(e))


def _log_complete_state():
    """Log complete state including local actuators and received sensors."""
    log("espnow_b", "=" * 60)
    log("espnow_b", "COMPLETE STATE SNAPSHOT (Board B)")
    log("espnow_b", "=" * 60)
    
    # Local actuator data (sent to A)
    modes = state.actuator_state["led_modes"]
    log("espnow_b", "LOCAL ACTUATORS (sent to A):")
    log("espnow_b", "  LEDs: Green={}, Blue={}, Red={}".format(
        modes.get("green", "off"), modes.get("blue", "off"), modes.get("red", "off")
    ))
    log("espnow_b", "  Servo: {}°".format(
        state.actuator_state["servo"].get("angle", "N/A")
    ))
    log("espnow_b", "  LCD: '{}' / '{}'".format(
        state.actuator_state["lcd"].get("line1", ""),
        state.actuator_state["lcd"].get("line2", "")
    ))
    log("espnow_b", "  Buzzer: {}, Audio: {}".format(
        "ON" if state.actuator_state["buzzer"].get("active", False) else "OFF",
        "PLAY" if state.actuator_state["audio"].get("playing", False) else "STOP"
    ))
    
    # Received sensor data from A
    log("espnow_b", "")
    log("espnow_b", "RECEIVED SENSORS (from A):")
    recv = state.received_sensor_state
    log("espnow_b", "  Temperature: {}°C".format(recv["temperature"] if recv["temperature"] is not None else "N/A"))
    log("espnow_b", "  CO: {} ppm".format(recv["co"] if recv["co"] is not None else "N/A"))
    log("espnow_b", "  Heart Rate: {} bpm, SpO2: {}%".format(
        recv["heart_rate_bpm"] if recv["heart_rate_bpm"] is not None else "N/A",
        recv["heart_rate_spo2"] if recv["heart_rate_spo2"] is not None else "N/A"
    ))
    log("espnow_b", "  Ultrasonic: {} cm".format(
        recv["ultrasonic_distance"] if recv["ultrasonic_distance"] is not None else "N/A"
    ))
    log("espnow_b", "  Buttons: B1={}, B2={}, B3={}".format(
        recv["button_b1"], recv["button_b2"], recv["button_b3"]
    ))
    log("espnow_b", "=" * 60)


def update():
    """Non-blocking update for ESP-NOW communication.
    
    Called periodically from main loop to receive sensor data from A
    and respond with actuator status.
    """
    global _messages_received
    
    if not _initialized or _esp_now is None:
        return
    
    try:
        # Check for sensor data from A
        mac, msg = _esp_now.irecv(0)
        if mac is not None and msg is not None:
            try:
                msg_str = msg.decode("utf-8")
                # Log disabled - uncomment for debugging
                # log("espnow_b", "[RX] {}".format(msg_str))
                _parse_sensor_state(msg_str)
                
                # Update ESP-NOW connection status
                from core import actuator_loop
                actuator_loop.set_espnow_connected(True)
                
                # Send actuator status as response
                _messages_received += 1
                actuator_status = _get_actuator_status_string()
                send_message(actuator_status)
            except:
                pass
        
        # Log complete state every 15 seconds
        if elapsed("espnow_state_log", _state_log_interval):
            _log_complete_state()
    except Exception as e:
        log("espnow_b", "Update error: {}".format(e))
