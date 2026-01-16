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
from core import state
from core.timers import elapsed
from config import config
try:
    import ujson as json  # type: ignore  # MicroPython
except ImportError:
    import json  # Fallback

# MAC addresses
MAC_A = bytes.fromhex("5C013B875310")  # Self (A)
MAC_B = bytes.fromhex("5C013B4C2C34")  # Remote (B)

# Send interval and message tracking
_send_interval = 2500  # Send sensor data every 2.5 seconds
REINIT_INTERVAL = 5000      # Try to recover ESP-NOW every 5 seconds when down
_state_log_interval = None  # Disabled snapshots
_message_count = 0
_version_mismatch_logged = False  # Prevent log spam

# Message ID tracking (prevent loops)
_next_msg_id = 1
_last_received_msg_id = 0
_pending_events = []  # Queue for immediate events

_esp_now = None
_initialized = False
_wifi = None
_last_init_attempt = 0


def _get_sensor_data_string(msg_type="data", msg_id=None):
    """Format all sensor data into a JSON message.
    
    Args:
        msg_type: Type of message - 'data' (periodic), 'event' (immediate), 'ack' (confirmation)
        msg_id: Message ID (auto-generated if None)
    """
    global _next_msg_id
    if msg_id is None:
        msg_id = _next_msg_id
        _next_msg_id += 1
    
    hr = state.sensor_data["heart_rate"]
    data = {
        "version": config.FIRMWARE_VERSION,
        "msg_type": msg_type,
        "msg_id": msg_id,
        "timestamp": ticks_ms(),
        "sensors": {
            "temperature": state.sensor_data.get("temperature"),
            "co": state.sensor_data.get("co"),
            "ultrasonic_distance": state.sensor_data.get("ultrasonic_distance_cm"),
            "presence_detected": state.sensor_data.get("ultrasonic_presence", False),
            "heart_rate": {
                "bpm": hr.get("bpm") if hr else None,
                "spo2": hr.get("spo2") if hr else None,
            }
        },
        "buttons": {
            "b1": state.button_state.get("b1", False),
            "b2": state.button_state.get("b2", False),
            "b3": state.button_state.get("b3", False),
        },
        "alarm": {
            "level": state.alarm_state.get("level", "normal"),
            "source": state.alarm_state.get("source")
        }
    }
    return json.dumps(data).encode("utf-8")


def init_espnow_comm():
    """Initialize ESP-NOW on Scheda A (Client mode).
    
    Client seeks connection to Scheda B (server).
    """
    global _esp_now, _initialized, _wifi, _last_init_attempt
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
        _last_init_attempt = ticks_ms()
        
        # Get actual MAC address
        try:
            actual_mac = _wifi.config('mac')
        except (AttributeError, OSError):
            actual_mac = MAC_A  # Fallback to configured MAC
        mac_str = ":".join("{:02X}".format(b) for b in actual_mac)
        
        log("communication.espnow", "ESP-NOW initialized (Client mode)")
        log("communication.espnow", "My MAC: {}".format(mac_str))
        log("communication.espnow", "Peer added: Scheda B ({})" .format(
            ":".join("{:02X}".format(b) for b in MAC_B)
        ))
        return True
    except Exception as e:
        log("communication.espnow", "Initialization failed: {}".format(e))
        _esp_now = None
        _initialized = False
        _last_init_attempt = ticks_ms()
        return False


def send_message(data):
    """Send message to Scheda B.
    
    Args:
        data: String or bytes to send
        
    Returns:
        True if message was sent, False otherwise
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
        log("espnow_a", "TX -> B len={} preview={}".format(len(data), preview))

        _esp_now.send(MAC_B, data)
        log("espnow_a", "TX OK to B")
        return True
    except Exception as e:
        log("communication.espnow", "Send error: {}".format(e))
        # Force a re-init on next update
        _initialized = False
        _esp_now = None
        return False


def send_event_immediate(event_type="alarm_triggered", custom_data=None):
    """Send an immediate event to Board B, bypassing the normal timer.
    
    Used for urgent notifications like alarm triggers, critical sensor readings, etc.
    
    Args:
        event_type: Type of event ('alarm_triggered', 'emergency', etc.)
        custom_data: Optional dict with additional event data
    
    Returns:
        True if queued/sent successfully
    """
    global _pending_events
    event_msg = {
        "event_type": event_type,
        "custom_data": custom_data or {}
    }
    _pending_events.append(event_msg)
    log("espnow_a", "Event queued: {}".format(event_type))
    return True


def _parse_actuator_state(msg_bytes):
    """Parse received actuator state from Board B (JSON format) and update state.
    
    Expected JSON format:
    {
        "version": 1,
        "type": "actuators",
        "timestamp": 12345678,
        "leds": {"green": "on", "blue": "blinking", "red": "off"},
        "servo": {"angle": 90},
        "lcd": {"line1": "Test", "line2": "Message"},
        "buzzer": "ON/OFF",
        "audio": "PLAY/STOP",
        "sos_active": false
    }
    
    Or heartbeat message:
    {
        "version": 1,
        "type": "heartbeat",
        "timestamp": 12345678
    }
    """
    try:
        msg_str = msg_bytes.decode("utf-8")
        log("espnow_a", "RX Parse: msg_str={}".format(msg_str[:100]))
        data = json.loads(msg_str)
        
        # Extract message metadata
        msg_id = data.get("msg_id", 0)
        msg_type = data.get("msg_type", "data")
        
        # Track received message ID to prevent duplicates
        global _last_received_msg_id
        if msg_id <= _last_received_msg_id and msg_type != "ack":
            log("espnow_a", "Duplicate msg_id={}, ignoring".format(msg_id))
            return None  # Return msg_id None to signal duplicate
        if msg_type != "ack":
            _last_received_msg_id = msg_id
        
        log("espnow_a", "RX msg_id={} type={}".format(msg_id, msg_type))
        
        # If this is just an ACK, don't update state, just return msg_id
        if msg_type == "ack":
            reply_to = data.get("reply_to_id")
            log("espnow_a", "ACK received for msg_id={}".format(reply_to))
            return msg_id  # Return to signal ACK processed
        
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
        
        # Parse LEDs
        leds = data.get("leds", {})
        state.received_actuator_state["leds"]["green"] = leds.get("green", "off")
        state.received_actuator_state["leds"]["blue"] = leds.get("blue", "off")
        state.received_actuator_state["leds"]["red"] = leds.get("red", "off")
        
        # Parse servo
        servo = data.get("servo", {})
        state.received_actuator_state["servo_angle"] = servo.get("angle")
        
        # Parse LCD
        lcd = data.get("lcd", {})
        state.received_actuator_state["lcd_line1"] = lcd.get("line1", "")
        state.received_actuator_state["lcd_line2"] = lcd.get("line2", "")
        
        # Parse audio devices
        state.received_actuator_state["buzzer"] = data.get("buzzer", "OFF")
        state.received_actuator_state["audio"] = data.get("audio", "STOP")
        state.received_actuator_state["last_update"] = ticks_ms()
        state.received_actuator_state["is_stale"] = False
        
        log("communication.espnow", "Actuator data received (v{}) msg_id={} type={} - LEDs=G:{},B:{},R:{} Servo={}°".format(
            remote_version,
            msg_id,
            msg_type,
            leds.get("green"),
            leds.get("blue"),
            leds.get("red"),
            servo.get("angle")
        ))
        log("espnow_a", "RX OK - Actuator state updated")
        return msg_id  # Return msg_id to send ACK
    except Exception as e:
        log("communication.espnow", "Parse error: {}".format(e))
        log("espnow_a", "RX Parse FAILED: {}".format(e))
        return None


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


def _parse_actuator_state_v0_fallback(msg_str):
    """Fallback parser for old string format (for backward compatibility).
    
    Old format: "V:1 ACTUATORS: LEDs=G:on,B:blinking,R:off Servo=90° LCD1='...' LCD2='...' Buzz=OFF Audio=STOP"
    """
    try:
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
        state.received_actuator_state["is_stale"] = False
        log("communication.espnow", "Parsed with v0 fallback format")
    except Exception as e:
        log("communication.espnow", "Fallback parse error: {}".format(e))


def update():
    """Non-blocking update for ESP-NOW communication.
    
    Called periodically from main loop to send sensor data
    and receive actuator status from B.
    
    Note: A continues normally if B is disconnected (sensor reads continue).
    """
    global _message_count
    
    if not _initialized or _esp_now is None:
        # Auto-recover ESP-NOW if it went down
        if elapsed("espnow_reinit", REINIT_INTERVAL):
            log("espnow_a", "ESP-NOW down, attempting re-init")
            init_espnow_comm()
        return
    
    # Check for incoming messages (actuator status from B)
    # Drain ALL pending messages to prevent buffer overflow
    messages_processed = 0
    max_messages_per_cycle = 10
    last_valid_msg = None
    
    while messages_processed < max_messages_per_cycle:
        try:
            mac, msg = _esp_now.irecv(0)
            
            if mac is None or msg is None:
                # No more messages available
                break
            
            messages_processed += 1
            last_valid_msg = msg
            
            try:
                mac_str = ":".join("{:02X}".format(b) for b in mac)
            except Exception:
                mac_str = str(mac)
            log("espnow_a", "RX from {} len={} preview={}".format(mac_str, len(msg), msg[:40]))
            
        except OSError:
            # OSError is normal when buffer is empty - silent break
            break
    
    # Process only the LAST received message (most recent data)
    if last_valid_msg is not None:
        if messages_processed > 1:
            log("espnow_a", "Drained {} messages, using latest".format(messages_processed))
        try:
            # Parse JSON actuator data from B (returns msg_id or None)
            _parse_actuator_state(last_valid_msg)
        except Exception as e:
            log("communication.espnow", "Parse error: {}".format(e))
    
    # Send pending events immediately (bypass timer)
    try:
        global _pending_events
        if _pending_events:
            event = _pending_events.pop(0)
            log("espnow_a", "Sending event: {}".format(event.get("event_type")))
            _message_count += 1
            sensor_data = _get_sensor_data_string(msg_type="event")
            send_message(sensor_data)
        # Send sensor data periodically (A is master, initiates communication)
        elif elapsed("espnow_send", _send_interval):
            _message_count += 1
            sensor_data = _get_sensor_data_string(msg_type="data")
            send_message(sensor_data)
    except Exception as e:
        log("communication.espnow", "Send error: {}".format(e))
    
    # Note: A does NOT go into standby if B disconnects.
    # Sensor reading and alarm logic continue normally.
    
    # Snapshot logging disabled
    if _state_log_interval and elapsed("espnow_state_log", _state_log_interval):
        try:
            _log_complete_state()
        except Exception as e:
            log("communication.espnow", "Log state error: {}".format(e))

