"""ESP-NOW bidirectional communication module for ESP32-A (Client mode).

Imported by: main.py, core.sensor_loop
Imports: espnow, network (MicroPython), time, debug.debug, core.state, 
         core.timers, config.config, ujson

ESP-NOW provides low-latency peer-to-peer communication between ESP32 boards
without requiring a WiFi router. This module implements the client side (Board A).

Board A (Client) responsibilities:
- Sends periodic sensor data snapshots to Board B (every 2.5s)
- Sends immediate event messages for critical situations
- Receives actuator status updates from Board B
- Receives command acknowledgments from Board B
- Forwards app commands from Node-RED to Board B
- Monitors connection health (timeout after 15s of no ACKs)

Message types:
1. "data": Periodic sensor snapshots (temp, CO, HR, ultrasonic, buttons, alarm)
2. "event": Immediate critical notifications (alarm critical, SOS, etc.)
3. "ack": Acknowledgments (confirm message receipt, prevent retransmission)
4. "command": Forwarded commands from Node-RED/app to Board B

MAC Addresses (hard-coded):
- Board A (self): 5C:01:3B:87:53:10
- Board B (peer): 5C:01:3B:4C:2C:34

JSON message format (compact keys to reduce packet size):
{
  "v": firmware_version,
  "t": message_type,
  "id": message_id,
  "ts": timestamp_ms,
  "s": {sensors},
  "B": {buttons},
  "A": {alarm},
  "r": reply_to_id (optional)
}

Connection management:
- Auto-reconnect if ESP-NOW fails (every 5s retry)
- Connection timeout detection (15s without ACK)
- Message ID tracking prevents duplicate processing
- Event retry (1 retry max for critical messages after 3s timeout)

Note: ESP-NOW requires WiFi to be active but does NOT require connection
to a router. It uses WiFi radio in peer-to-peer mode.
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

# Communication quality tracking
_stats_tx_total = 0      # Total messages sent
_stats_rx_total = 0      # Total valid messages received
_stats_rx_corrupted = 0  # Messages failed validation or JSON parse
_stats_last_log = 0      # Last time stats were logged
STATS_LOG_INTERVAL = 60000  # Log stats every 60 seconds

# Message ID tracking (prevent loops)
_next_msg_id = 1
_last_received_msg_id = 0
_pending_events = []  # Queue for immediate events

# Event retry tracking (max 1 retry for critical events)
EVENT_RETRY_TIMEOUT = 3000  # Retry after 3 seconds if no ACK
_pending_event_acks = {}  # {msg_id: {"msg": data, "sent_at": timestamp, "retry_count": 0}}

# Connection tracking (heartbeat/ACK timeout detection)
CONNECTION_TIMEOUT = 15000  # Consider B disconnected if no ACK for 15 seconds
_last_ack_from_b = 0  # Timestamp of last ACK received from B
_b_is_connected = False  # Connection state tracking

_esp_now = None
_initialized = False
_wifi = None
_last_init_attempt = 0


def _get_sensor_data_string(msg_type="data", msg_id=None, reply_to_id=None):
    """Format all sensor data into a JSON message.
    
    Args:
        msg_type: Type of message - 'data' (periodic), 'event' (immediate), 'ack' (confirmation)
        msg_id: Message ID (auto-generated if None)
        reply_to_id: ID of message this is replying to (for ACKs)
    
    Returns:
        JSON bytes with guaranteed field order and minimal size
    """
    global _next_msg_id
    if msg_id is None:
        msg_id = _next_msg_id
        _next_msg_id += 1
    
    hr = state.sensor_data["heart_rate"]
    
    # Get sensor values
    temp = state.sensor_data.get("temperature")
    co = state.sensor_data.get("co")
    dist = state.sensor_data.get("ultrasonic_distance_cm")
    presence = state.sensor_data.get("ultrasonic_presence", False)
    bpm = hr.get("bpm") if hr else None
    spo2 = hr.get("spo2") if hr else None
    b1 = state.button_state.get("b1", False)
    b2 = state.button_state.get("b2", False)
    b3 = state.button_state.get("b3", False)
    alarm_level = state.alarm_state.get("level", "normal")
    alarm_source = state.alarm_state.get("source")
    
    # Manual JSON construction to guarantee field order and minimal size
    # This ensures compatibility with MicroPython ujson which doesn't preserve dict order
    # Using list + join() for efficiency (string concatenation in loop is very slow in MicroPython)
    
    parts = [
        "{\"v\":", str(config.FIRMWARE_VERSION), ",",
        "\"t\":\"", msg_type, "\",",
        "\"id\":", str(msg_id), ",",
        "\"ts\":", str(ticks_ms()), ",",
        "\"s\":{",
        "\"T\":", ("null" if temp is None else str(temp)), ",",
        "\"C\":", ("null" if co is None else str(co)), ",",
        "\"U\":", ("null" if dist is None else str(dist)), ",",
        "\"P\":", ("true" if presence else "false"), ",",
        "\"H\":{",
        "\"b\":", ("null" if bpm is None else str(bpm)), ",",
        "\"o\":", ("null" if spo2 is None else str(spo2)),
        "}},",
        "\"B\":{",
        "\"1\":", ("true" if b1 else "false"), ",",
        "\"2\":", ("true" if b2 else "false"), ",",
        "\"3\":", ("true" if b3 else "false"),
        "},",
        "\"A\":{",
        "\"L\":\"", str(alarm_level), "\",",
        "\"S\":", ("null" if alarm_source is None else "\"" + str(alarm_source) + "\""),
        "}",
    ]
    
    if reply_to_id is not None:
        parts.append(",\"r\":")
        parts.append(str(reply_to_id))
    
    parts.append("}")
    json_str = "".join(parts)
    msg_bytes = json_str.encode("utf-8")
    
    # Check ESP-NOW size limit (250 bytes max)
    if len(msg_bytes) > 250:
        log("communication.espnow", "WARNING: Message too large ({} bytes, max 250). May be truncated!".format(len(msg_bytes)))
    
    # Verify JSON is valid before sending
    try:
        json.loads(json_str)
    except Exception as e:
        log("communication.espnow", "ERROR: Invalid JSON generated: " + str(e))
        log("communication.espnow", "JSON string: " + json_str[:150])
    
    return msg_bytes


def init_espnow_comm():
    """Initialize ESP-NOW on Scheda A (Client mode).
    
    Client seeks connection to Scheda B (server).
    """
    global _esp_now, _initialized, _wifi, _last_init_attempt
    try:
        # Clean up any existing ESP-NOW instance first
        if _esp_now is not None:
            try:
                _esp_now.active(False)
            except:
                pass  # Ignore errors during cleanup
            _esp_now = None
        
        # Get WiFi interface in station mode for ESP-NOW
        _wifi = network.WLAN(network.STA_IF)
        _wifi.active(True)
        
        # Note: Do NOT set WiFi channel after WiFi STA is connected
        # ESP-NOW will use the channel of the connected network
        # Attempting to set channel while STA is active causes "WiFi Internal State Error"
        
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
        # Check if error is because ESP-NOW already exists
        error_str = str(e)
        if "ESP_ERR_ESPNOW_EXIST" in error_str or "-12395" in error_str:
            # ESP-NOW already active, consider it initialized
            log("communication.espnow", "ESP-NOW already active, reusing instance")
            _initialized = True
            _last_init_attempt = ticks_ms()
            return True
        else:
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
        
        # Check size (ESP-NOW max is 250 bytes)
        if len(data) > 250:
            log("communication.espnow", "ERROR: Message too large ({} bytes, max 250)".format(len(data)))
            return False
        
        # Log after successful send with full context
        msg_id = "?"
        msg_type = "?"
        try:
            msg_dict = json.loads(data.decode("utf-8"))
            msg_id = msg_dict.get("id", "?")
            msg_type = msg_dict.get("t", msg_dict.get("msg_type", "?"))
        except Exception:
            pass  # Best-effort parsing only for logging

        _esp_now.send(MAC_B, data)
        log("espnow_a", "TX OK -> B id={} type={} len={}".format(msg_id, msg_type, len(data)))
        
        # Update stats
        global _stats_tx_total
        _stats_tx_total += 1
        
        return True
    except Exception as e:
        log("communication.espnow", "Send error: {}".format(e))
        # Force a re-init on next update
        _initialized = False
        _esp_now = None
        return False


def _check_event_retry():
    """Check pending events and retry if no ACK received within timeout (max 1 retry)."""
    global _pending_event_acks
    
    now = ticks_ms()
    to_remove = []
    
    for msg_id, event_info in _pending_event_acks.items():
        elapsed_time = ticks_diff(now, event_info["sent_at"])
        
        # If timeout and retry not exhausted, retry once
        if elapsed_time > EVENT_RETRY_TIMEOUT:
            if event_info["retry_count"] < 1:
                # Retry once
                log("espnow_a", "Event msg_id={} timeout, retrying (attempt 2/2)".format(msg_id))
                send_message(event_info["msg"])
                event_info["sent_at"] = now
                event_info["retry_count"] += 1
            else:
                # Max retry reached, give up
                log("espnow_a", "Event msg_id={} failed after 1 retry, giving up".format(msg_id))
                to_remove.append(msg_id)
    
    # Clean up failed events
    for msg_id in to_remove:
        del _pending_event_acks[msg_id]


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


def send_command(command_dict):
    """Send a command to Board B via ESP-NOW.
    
    Converts a command dict to JSON and sends immediately.
    
    Args:
        command_dict: Dict with keys:
            - target: "B" (destination board)
            - command: "servo", "led", etc.
            - args: [arg1, arg2, ...] (command arguments)
            - _source: source of command (e.g., "app")
            - _session_id: session ID for tracking
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        if not command_dict or command_dict.get("target") != "B":
            log("espnow_a", "send_command: Invalid target")
            return False
        
        # Format command as JSON
        msg = json.dumps(command_dict).encode("utf-8")
        
        # Send immediately
        if send_message(msg):
            log("espnow_a", "Command sent: {} {}".format(
                command_dict.get("command"), command_dict.get("args", [])
            ))
            return True
        else:
            log("espnow_a", "Command send failed")
            return False
    
    except Exception as e:
        log("communication.espnow", "send_command error: {}".format(e))
        return False


def _validate_message(msg_bytes):
    """Validate message structure before JSON parsing.
    
    Returns:
        True if message looks valid, False otherwise
    """
    # Check type
    if not isinstance(msg_bytes, (bytes, bytearray)):
        log("espnow_a", "Invalid message type: {}".format(type(msg_bytes)))
        return False
    
    # Check not empty
    if len(msg_bytes) == 0:
        log("espnow_a", "Empty message received")
        return False
    
    # NOTE: Don't strip null bytes here - let _parse_actuator_state handle it
    # This function only validates structure, doesn't modify data
    msg_bytes_for_check = bytes(msg_bytes).rstrip(b'\x00') if isinstance(msg_bytes, (bytes, bytearray)) else msg_bytes
    
    # Check if it starts with '{' (JSON)
    if len(msg_bytes_for_check) > 0 and msg_bytes_for_check[0:1] != b'{':
        log("espnow_a", "Message doesn't start with '{{': preview={}".format(msg_bytes_for_check[:20]))
        return False
    
    # Check if it ends with '}'
    if len(msg_bytes_for_check) > 0 and msg_bytes_for_check[-1:] != b'}':
        log("espnow_a", "Message doesn't end with '}}': preview={}".format(msg_bytes_for_check[-20:]))
        return False
    
    # Basic UTF-8 validation
    try:
        msg_bytes_for_check.decode("utf-8")
    except UnicodeDecodeError:
        log("espnow_a", "Message is not valid UTF-8")
        return False
    
    return True


def _parse_actuator_state(msg_bytes):
    """Parse received actuator state from Board B (JSON format) and update state.
    
    Supports both compact and full JSON formats:
    
    Compact format (v=version, t=type, id=msg_id, L=leds, etc.):
    {"v":1,"t":"data","id":1,"ts":9622,"L":{"g":"on","b":"off","r":"off"},"S":{"a":90},"D":{"1":"Line 1","2":"Line 2"},"B":"OFF","A":"STOP","O":false}
    
    Full format (for backward compatibility):
    {"version":1,"msg_type":"data","msg_id":1,"timestamp":12345,"leds":{"green":"on","blue":"off","red":"off"},"servo":{"angle":90},"lcd":{"line1":"Line 1","line2":"Line 2"},"buzzer":"OFF","audio":"STOP","sos_active":false}
    
    Or heartbeat message:
    {"v":1,"t":"heartbeat","ts":12345678} or {"version":1,"type":"heartbeat","timestamp":12345678}
    """
    try:
        # Validate message structure first
        if not _validate_message(msg_bytes):
            return None
        
        # Convert bytearray to bytes if needed
        if isinstance(msg_bytes, bytearray):
            msg_bytes = bytes(msg_bytes)
        
        # CRITICAL FIX: Strip trailing null bytes that ESP-NOW pads to 250 bytes
        # ESP-NOW pads every message to 250-byte boundary with zeros
        # Board B also pads with nulls, so we strip ALL trailing zeros
        msg_bytes_original = msg_bytes
        msg_bytes = msg_bytes.rstrip(b'\x00')
        
        # Only log if padding was actually removed
        if len(msg_bytes) != len(msg_bytes_original):
            log("espnow_a", "RX Stripped {} bytes of padding".format(len(msg_bytes_original) - len(msg_bytes)))
        
        # Decode bytes to string
        try:
            msg_str = msg_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            log("espnow_a", "RX Decode error (not valid UTF-8): {}".format(e))
            log("espnow_a", "Raw bytes preview: {}".format(msg_bytes[:80]))
            return None
        
        log("espnow_a", "RX Parse: msg_str length={} bytes".format(len(msg_str)))
        
        # Try to parse JSON
        try:
            data = json.loads(msg_str)
        except ValueError as e:  # json.JSONDecodeError inherits from ValueError
            log("espnow_a", "RX JSON parse error: {} | JSON preview: {}".format(str(e), msg_str[:100]))
            # Check if JSON is truncated (missing closing brace)
            if not msg_str.rstrip().endswith('}'):
                log("espnow_a", "JSON appears truncated (no closing brace), len={}".format(len(msg_str)))
            # Update stats: JSON parse failed
            global _stats_rx_corrupted
            _stats_rx_corrupted += 1
            # Try fallback parser for old format
            _parse_actuator_state_v0_fallback(msg_str)
            return None
        
        # Detect format (compact uses 'v', full uses 'version')
        is_compact = "v" in data
        
        # Extract message metadata
        if is_compact:
            msg_id = data.get("id", 0)
            msg_type = data.get("t", "data")
            remote_version = data.get("v")
        else:
            msg_id = data.get("msg_id", 0)
            msg_type = data.get("msg_type", "data")
            remote_version = data.get("version")
        
        # Track received message ID to prevent duplicates
        global _last_received_msg_id
        if msg_id <= _last_received_msg_id and msg_type != "ack":
            log("espnow_a", "Duplicate msg_id={}, ignoring".format(msg_id))
            return None  # Return msg_id None to signal duplicate
        if msg_type != "ack":
            _last_received_msg_id = msg_id
        
        log("espnow_a", "RX msg_id={} type={} fmt={}".format(msg_id, msg_type, "compact" if is_compact else "full"))
        
        # If this is just an ACK, don't update state and DON'T send another ACK back
        if msg_type == "ack":
            reply_to = data.get("r" if is_compact else "reply_to_id")
            log("espnow_a", "ACK received for msg_id={}".format(reply_to))
            
            # Update connection heartbeat
            global _last_ack_from_b
            _last_ack_from_b = ticks_ms()
            
            # Remove from pending events if it was an event waiting for ACK
            global _pending_event_acks
            if reply_to in _pending_event_acks:
                del _pending_event_acks[reply_to]
                log("espnow_a", "Event msg_id={} confirmed, removed from pending".format(reply_to))
            
            return -1  # Special code: ACK received, don't respond with another ACK
        
        # Check version (warning only, don't block communication)
        if remote_version != config.FIRMWARE_VERSION:
            global _version_mismatch_logged
            if not _version_mismatch_logged:
                log("communication.espnow", "WARNING: Firmware version mismatch! Local=v{}, Remote=v{}".format(
                    config.FIRMWARE_VERSION, remote_version
                ))
                _version_mismatch_logged = True
        else:
            _version_mismatch_logged = False
        
        # Parse actuators (support both formats)
        if is_compact:
            leds = data.get("L", {})
            state.received_actuator_state["leds"]["green"] = leds.get("g", "off")
            state.received_actuator_state["leds"]["blue"] = leds.get("b", "off")
            state.received_actuator_state["leds"]["red"] = leds.get("r", "off")
            
            # Parse servo (compact)
            servo = data.get("S", {})
            state.received_actuator_state["servo_angle"] = servo.get("a")
            
            # Parse LCD (compact)
            lcd = data.get("D", {})
            state.received_actuator_state["lcd_line1"] = lcd.get("1", "")
            state.received_actuator_state["lcd_line2"] = lcd.get("2", "")
            
            # Parse audio devices (compact)
            state.received_actuator_state["buzzer"] = data.get("B", "OFF")
            state.received_actuator_state["audio"] = data.get("A", "STOP")
            # Parse SOS mode (compact)
            state.received_actuator_state["sos_mode"] = bool(data.get("O", False))
        else:
            # Full format (backward compatibility)
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
            # Parse SOS mode (full format)
            state.received_actuator_state["sos_mode"] = bool(data.get("sos_active", False))
        
        state.received_actuator_state["last_update"] = ticks_ms()
        state.received_actuator_state["is_stale"] = False
        
        log("communication.espnow", "Actuator data received (v{}) msg_id={} type={} - LEDs=G:{},B:{},R:{} Servo={}° SOS={}".format(
            remote_version,
            msg_id,
            msg_type,
            state.received_actuator_state["leds"]["green"],
            state.received_actuator_state["leds"]["blue"],
            state.received_actuator_state["leds"]["red"],
            state.received_actuator_state["servo_angle"],
            state.received_actuator_state.get("sos_mode")
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
    log("espnow_a", "  SOS Mode: {}".format(recv.get("sos_mode", False)))
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
    global _message_count, _last_ack_from_b, _b_is_connected, _last_received_msg_id
    
    if not _initialized or _esp_now is None:
        # Auto-recover ESP-NOW if it went down
        if elapsed("espnow_reinit", REINIT_INTERVAL):
            log("espnow_a", "ESP-NOW down, attempting re-init")
            init_espnow_comm()
        return
    
    # Check if B is still connected (heartbeat timeout check)
    now = ticks_ms()
    if _last_ack_from_b > 0:
        elapsed_since = ticks_diff(now, _last_ack_from_b)
        if elapsed_since > CONNECTION_TIMEOUT:
            if _b_is_connected:
                log("communication.espnow", "WARNING: Board B disconnected (no ACK for 15s)")
                _b_is_connected = False
                # Reset msg_id counter for re-sync when B reconnects
                _last_received_msg_id = 0
                log("communication.espnow", "Reset message ID counter for re-sync")
        else:
            if not _b_is_connected:
                log("communication.espnow", "Board B reconnected")
                _b_is_connected = True
    
    # Check for incoming messages (actuator status from B)
    # Drain ALL pending messages to prevent buffer overflow
    messages_processed = 0
    max_messages_per_cycle = 10
    valid_messages = []  # Store all valid messages
    
    while messages_processed < max_messages_per_cycle:
        try:
            mac, msg = _esp_now.irecv(0)
            
            if mac is None or msg is None:
                # No more messages available
                break
            
            messages_processed += 1
            
            try:
                mac_str = ":".join("{:02X}".format(b) for b in mac)
            except Exception:
                mac_str = str(mac)
            log("espnow_a", "RX from {} len={} preview={}".format(mac_str, len(msg), msg[:40]))
            
            # Validate message before storing
            if _validate_message(msg):
                valid_messages.append(msg)
                # Update stats: valid message received
                global _stats_rx_total
                _stats_rx_total += 1
            else:
                log("espnow_a", "Message validation failed, skipping")
                # Update stats: corrupted message
                global _stats_rx_corrupted
                _stats_rx_corrupted += 1
            
        except OSError:
            # OSError is normal when buffer is empty - silent break
            break
    
    # Process the FIRST valid message (most likely to be complete)
    if valid_messages:
        if messages_processed > 1:
            log("espnow_a", "Drained {} messages ({} valid), using first valid".format(
                messages_processed, len(valid_messages)))
        
        # Use first valid message
        msg_to_process = valid_messages[0]
        try:
            # Parse JSON actuator data from B (returns msg_id, -1 for ACK, or None for error)
            received_msg_id = _parse_actuator_state(msg_to_process)
            
            # Send ACK if we successfully parsed a data or event message
            # Don't send ACK for ACKs (received_msg_id == -1)
            if received_msg_id is not None and received_msg_id > 0:
                ack_msg = _get_sensor_data_string(msg_type="ack", reply_to_id=received_msg_id)
                send_message(ack_msg)
                log("espnow_a", "Sent ACK for msg_id={}".format(received_msg_id))
        except Exception as e:
            log("communication.espnow", "Parse error: {}".format(e))
    
    # Check for events that need retry (no ACK received within timeout)
    _check_event_retry()
    
    # Send pending events immediately (bypass timer)
    try:
        global _pending_events, _pending_event_acks
        if _pending_events:
            event = _pending_events.pop(0)
            log("espnow_a", "Sending event: {}".format(event.get("event_type")))
            _message_count += 1
            
            # Get message ID for tracking
            msg_id = _next_msg_id
            sensor_data = _get_sensor_data_string(msg_type="event", msg_id=msg_id)
            
            # Track this event for ACK confirmation (max 1 retry)
            _pending_event_acks[msg_id] = {
                "msg": sensor_data,
                "sent_at": ticks_ms(),
                "retry_count": 0
            }
            
            send_message(sensor_data)
        # Send sensor data periodically (A is master, initiates communication)
        elif elapsed("espnow_send", _send_interval):
            _message_count += 1
            sensor_data = _get_sensor_data_string(msg_type="data")
            send_message(sensor_data)  # Periodic data doesn't need retry
    except Exception as e:
        log("communication.espnow", "Send error: {}".format(e))
    
    # Note: A does NOT go into standby if B disconnects.
    # Sensor reading and alarm logic continue normally.
    
    # Log communication quality stats periodically
    global _stats_last_log, _stats_tx_total, _stats_rx_total, _stats_rx_corrupted
    if elapsed("espnow_stats_log", STATS_LOG_INTERVAL):
        total_rx = _stats_rx_total + _stats_rx_corrupted
        if total_rx > 0:
            success_rate = (_stats_rx_total / total_rx) * 100
            log("espnow_a", "Stats: TX={} RX={} Corrupted={} Success={:.1f}%".format(
                _stats_tx_total, _stats_rx_total, _stats_rx_corrupted, success_rate))
        else:
            log("espnow_a", "Stats: TX={} RX=0 (no messages received)".format(_stats_tx_total))
    
    # Snapshot logging disabled
    if _state_log_interval and elapsed("espnow_state_log", _state_log_interval):
        try:
            _log_complete_state()
        except Exception as e:
            log("communication.espnow", "Log state error: {}".format(e))

