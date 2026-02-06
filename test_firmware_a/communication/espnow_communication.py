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
- Board A (self): 5C:01:3B:4C:2C:34
- Board B (peer): 5C:01:3B:87:53:10

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
MAC_A = bytes.fromhex("5C013B4C2C34")  # Self (A)
MAC_B = bytes.fromhex("d8bc38e470bc")  # Remote (B)

# Send interval and message tracking
_send_interval = 200  # Send sensor data every 200ms (was 2.5s - now responsive)
REINIT_INTERVAL = 5000      # Try to recover ESP-NOW every 5 seconds when down
_message_count = 0

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
    sos_mode = state.alarm_state.get("sos_mode", False)
    
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
        "\"S\":", ("null" if alarm_source is None else "\"" + str(alarm_source) + "\""), ",",
        "\"M\":", ("true" if sos_mode else "false"),
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
        _esp_now.send(MAC_B, data)
        log("espnow_a", "TX: type={} len={}".format(msg_type, len(data)))
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
                send_message(event_info["msg"])
                event_info["sent_at"] = now
                event_info["retry_count"] += 1
            else:
                # Max retry reached, give up
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
    {"v":1,"t":"data","id":1,"ts":9622,"L":{"g":"on","b":"off","r":"off"},"S":{"a":180},"D":{"1":"Line 1","2":"Line 2"},"B":"OFF","A":"STOP","O":false}
    
    Full format (for backward compatibility):
    {"version":1,"msg_type":"data","msg_id":1,"timestamp":12345,"leds":{"green":"on","blue":"off","red":"off"},"servo":{"angle":180},"lcd":{"line1":"Line 1","line2":"Line 2"},"buzzer":"OFF","audio":"STOP","sos_active":false}
    
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
        
        # Extract message metadata (only compact format now)
        msg_id = data.get("id", 0)
        msg_type = data.get("t", "data")
        remote_version = data.get("v")
        
        # Track received message ID to prevent duplicates
        global _last_received_msg_id
        if msg_id <= _last_received_msg_id and msg_type != "ack":
            log("espnow_a", "Duplicate msg_id={}, ignoring".format(msg_id))
            return None  # Return msg_id None to signal duplicate
        if msg_type != "ack":
            _last_received_msg_id = msg_id
        
        log("espnow_a", "RX: msg_id={} type={}".format(msg_id, msg_type))
        
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
            log("communication.espnow", "WARNING: Firmware version mismatch! Local=v{}, Remote=v{}".format(
                config.FIRMWARE_VERSION, remote_version
            ))
        
        # Parse actuators (compact format only)
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
        
        state.received_actuator_state["last_update"] = ticks_ms()
        state.received_actuator_state["is_stale"] = False
        
        # SYNC: Update local gate_state based on servo angle from ESP32-B
        # This keeps ESP32-A, ESP32-B, and app in sync
        servo_angle = state.received_actuator_state.get("servo_angle")
        if servo_angle is not None:
            # Gate is open when servo is at 180°, closed at 0°
            # Use threshold: >90° = open, <=90° = closed
            gate_is_open = servo_angle > 90
            if state.gate_state.get("gate_open") != gate_is_open:
                state.gate_state["gate_open"] = gate_is_open
                log("espnow_a", "SYNC: gate_open updated to {} (servo={}°)".format(gate_is_open, servo_angle))
                # Request immediate publish to update app with new gate state
                try:
                    from communication import nodered_client
                    nodered_client.request_publish_now()
                except Exception:
                    pass  # Ignore if nodered_client not available
        
        # SYNC: Update local alarm_state["sos_mode"] based on sos_mode from ESP32-B
        # If ESP32-B activates SOS via physical button, propagate it to alarm_state and app
        sos_from_b = state.received_actuator_state.get("sos_mode", False)
        if sos_from_b != state.alarm_state.get("sos_mode", False):
            state.alarm_state["sos_mode"] = sos_from_b
            if sos_from_b:
                # SOS activated on board B - set alarm to danger/manual
                state.alarm_state["level"] = "danger"
                state.alarm_state["source"] = "manual"
                log("espnow_a", "SYNC: SOS activated from ESP32-B button - alarm set to danger/manual")
            else:
                # SOS deactivated on board B - clear alarm (only if not triggered by sensors)
                # Check if any sensor is still critical before clearing
                if state.alarm_state.get("level") == "danger" and state.alarm_state.get("source") == "manual":
                    state.alarm_state["level"] = "normal"
                    state.alarm_state["source"] = None
                    log("espnow_a", "SYNC: SOS deactivated from ESP32-B button - alarm cleared")
            # Request immediate publish to update app
            try:
                from communication import nodered_client
                nodered_client.request_publish_now()
            except Exception:
                pass  # Ignore if nodered_client not available
        
        log("communication.espnow", "RX: Actuators - LEDs=G:{},B:{},R:{} Servo={}°".format(
            state.received_actuator_state["leds"]["green"],
            state.received_actuator_state["leds"]["blue"],
            state.received_actuator_state["leds"]["red"],
            state.received_actuator_state["servo_angle"]
        ))
        return msg_id  # Return msg_id to send ACK
    except Exception as e:
        log("communication.espnow", "Parse error: {}".format(e))
        log("espnow_a", "RX Parse FAILED: {}".format(e))
        return None


def _log_complete_state():
    """Log complete state including local sensors and received actuators."""
    # Removed - logging functionality simplified



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
            log("espnow_a", "RX len={}".format(len(msg)))
            
            # Validate message before storing
            if _validate_message(msg):
                valid_messages.append(msg)
            else:
                log("espnow_a", "RX: Message validation failed")
            
        except OSError:
            # OSError is normal when buffer is empty - silent break
            break
    
    # Process the FIRST valid message (most likely to be complete)
    if valid_messages:
        if messages_processed > 1:
            log("espnow_a", "RX: Drained {} messages, using first".format(messages_processed))
        
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
    if elapsed("espnow_state_log", 60000):
        try:
            _log_complete_state()
        except Exception as e:
            log("communication.espnow", "Log state error: {}".format(e))

