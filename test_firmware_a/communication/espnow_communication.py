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
from time import ticks_ms  # type: ignore
from debug.debug import log
from core import state
from core.timers import elapsed
from config import config

# MAC addresses
MAC_A = bytes.fromhex("5C013B875310")  # Self (A)
MAC_B = bytes.fromhex("5C013B4C2C34")  # Remote (B)

_esp_now = None
_initialized = False
_wifi = None
_send_interval = 5000  # Send sensor data every 5 seconds
_state_log_interval = 15000  # Log complete state every 15 seconds
_message_count = 0
_version_mismatch_logged = False  # Prevent log spam


def _get_sensor_data_string():
    """Format all sensor data into a compact string."""
    hr = state.sensor_data["heart_rate"]
    data = "V:{} SENSORS: Temp={} CO={} HR={} SpO2={} Dist={} Btns={}|{}|{}".format(
        config.FIRMWARE_VERSION,
        state.sensor_data.get("temperature", "N/A"),
        state.sensor_data.get("co", "N/A"),
        hr.get("bpm", "N/A") if hr else "N/A",
        hr.get("spo2", "N/A") if hr else "N/A",
        state.sensor_data.get("ultrasonic_distance_cm", "N/A"),
        state.button_state.get("b1", False),
        state.button_state.get("b2", False),
        state.button_state.get("b3", False)
    )
    return data


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
        try:
            actual_mac = _wifi.config('mac')
        except (AttributeError, OSError):
            actual_mac = MAC_A  # Fallback to configured MAC
        mac_str = ":".join("{:02X}".format(b) for b in actual_mac)
        
        log("espnow_a", "ESP-NOW initialized (Client mode)")
        log("espnow_a", "My MAC: {}".format(mac_str))
        log("espnow_a", "Peer added: Scheda B ({})" .format(
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
    if not _initialized or _esp_now is None:
        log("espnow_a", "ESP-NOW not initialized")
        return False
    
    try:
        if isinstance(data, str):
            data = data.encode("utf-8")
        
        _esp_now.send(MAC_B, data)
        return True
    except Exception as e:
        log("espnow_a", "Send error: {}".format(e))
        return False


def _parse_actuator_state(msg_str):
    """Parse received actuator state from Board B and update state.
    
    Expected format: "V:1 ACTUATORS: LEDs=G:on,B:blinking,R:off Servo=90° LCD1='...' LCD2='...' Buzz=OFF Audio=STOP"
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
                        log("espnow_a", "ERROR: Firmware version mismatch! Local=v{}, Remote=v{}".format(
                            config.FIRMWARE_VERSION, remote_version
                        ))
                        _version_mismatch_logged = True
                    return  # Ignore message due to version mismatch
                else:
                    _version_mismatch_logged = False  # Reset flag when versions match
            except:
                pass
        
        # Simple parsing - extract key values
        if "LEDs=G:" in msg_str:
            parts = msg_str.split("LEDs=G:")[1].split(",B:")
            state.received_actuator_state["leds"]["green"] = parts[0].strip()
            
            parts2 = parts[1].split(",R:")
            state.received_actuator_state["leds"]["blue"] = parts2[0].strip()
            state.received_actuator_state["leds"]["red"] = parts2[1].split()[0].strip()
        
        if "Servo=" in msg_str:
            servo_str = msg_str.split("Servo=")[1].split("°")[0].strip()
            try:
                state.received_actuator_state["servo_angle"] = int(servo_str) if servo_str != "N/A" else None
            except:
                state.received_actuator_state["servo_angle"] = None
        
        if "LCD1='" in msg_str:
            lcd1_str = msg_str.split("LCD1='")[1].split("'")[0]
            state.received_actuator_state["lcd_line1"] = lcd1_str
        
        if "LCD2='" in msg_str:
            lcd2_str = msg_str.split("LCD2='")[1].split("'")[0]
            state.received_actuator_state["lcd_line2"] = lcd2_str
        
        if "Buzz=" in msg_str:
            buzz_str = msg_str.split("Buzz=")[1].split()[0].strip()
            state.received_actuator_state["buzzer"] = buzz_str
        
        if "Audio=" in msg_str:
            audio_str = msg_str.split("Audio=")[1].strip()
            state.received_actuator_state["audio"] = audio_str
        
        state.received_actuator_state["last_update"] = ticks_ms()
    except Exception as e:
        log("espnow_a", "Parse error: {}".format(e))


def _log_complete_state():
    """Log complete state including local sensors and received actuators."""
    log("espnow_a", "=" * 60)
    log("espnow_a", "COMPLETE STATE SNAPSHOT (Board A)")
    log("espnow_a", "=" * 60)
    
    # Local sensor data (sent to B)
    hr = state.sensor_data.get("heart_rate", {})
    log("espnow_a", "LOCAL SENSORS (sent to B):")
    log("espnow_a", "  Temperature: {}°C".format(state.sensor_data.get("temperature", "N/A")))
    log("espnow_a", "  CO: {} ppm".format(state.sensor_data.get("co", "N/A")))
    log("espnow_a", "  Heart Rate: {} bpm, SpO2: {}%".format(
        hr.get("bpm", "N/A") if hr else "N/A",
        hr.get("spo2", "N/A") if hr else "N/A"
    ))
    log("espnow_a", "  Ultrasonic: {} cm".format(state.sensor_data.get("ultrasonic_distance_cm", "N/A")))
    log("espnow_a", "  Buttons: B1={}, B2={}, B3={}".format(
        state.button_state.get("b1", False),
        state.button_state.get("b2", False),
        state.button_state.get("b3", False)
    ))
    
    # Received actuator data from B
    log("espnow_a", "")
    log("espnow_a", "RECEIVED ACTUATORS (from B):")
    recv = state.received_actuator_state
    log("espnow_a", "  LEDs: G={}, B={}, R={}".format(
        recv["leds"]["green"], recv["leds"]["blue"], recv["leds"]["red"]
    ))
    log("espnow_a", "  Servo: {}°".format(recv["servo_angle"] if recv["servo_angle"] is not None else "N/A"))
    log("espnow_a", "  LCD: '{}' / '{}'".format(recv["lcd_line1"], recv["lcd_line2"]))
    log("espnow_a", "  Buzzer: {}, Audio: {}".format(recv["buzzer"], recv["audio"]))
    log("espnow_a", "=" * 60)


def update():
    """Non-blocking update for ESP-NOW communication.
    
    Called periodically from main loop to send sensor data
    and receive actuator status from B.
    """
    global _message_count
    
    if not _initialized or _esp_now is None:
        return
    
    try:
        # Check for incoming messages (actuator status from B)
        mac, msg = _esp_now.irecv(0)
        if mac is not None and msg is not None:
            try:
                msg_str = msg.decode("utf-8")
                # Log disabled - uncomment for debugging
                # log("espnow_a", "[RX] {}".format(msg_str))
                _parse_actuator_state(msg_str)
            except:
                pass
        
        # Send sensor data periodically
        if elapsed("espnow_send", _send_interval):
            _message_count += 1
            sensor_data = _get_sensor_data_string()
            send_message(sensor_data)
        
        # Log complete state every 15 seconds
        if elapsed("espnow_state_log", _state_log_interval):
            _log_complete_state()
    except Exception as e:
        log("espnow_a", "Update error: {}".format(e))
