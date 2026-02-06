"""ESP-NOW communication module for ESP32-B (Actuator Board - Server).

Imported by: main.py
Imports: espnow, network, time, ujson, debug.debug, core.state, core.timers, config.config

Board B acts as ESP-NOW server:
- Waits for incoming connections from Board A (client)
- Receives sensor data and alarm state from Board A
- Can send acknowledgments or actuator state back to Board A

MAC Addresses:
- Board B (self): 5C:01:3B:87:53:10
- Board A (remote): 5C:01:3B:4C:2C:34

Message format (JSON):
{
    "msg_id": 123,
    "sensor_state": {...},
    "alarm_level": "danger"
}

Connection tracking:
- Marks Board A as disconnected if no message received for 10s
- Triggers alarm indicator shutdown on disconnect
- Auto-reinitializes ESP-NOW every 5s if module fails

Packet ID tracking prevents duplicate processing if Board A reboots.
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
MAC_B = bytes.fromhex("d8bc38e470bc")  # Self (B)
MAC_A = bytes.fromhex("5C013B4C2C34")  # Remote (A)

# Connection tracking and message IDs
CONNECTION_TIMEOUT = 10000  # Consider A disconnected if no message for 10 seconds (4x send interval)
REINIT_INTERVAL = 5000      # Try to recover ESP-NOW every 5 seconds when down
_last_message_from_a = 0
_a_is_connected = False
_messages_received = 0

# Message ID tracking (prevent loops)
_next_msg_id = 1
_last_received_msg_id = 0
_pending_events = []  # Queue for immediate events (e.g., SOS activation)

# Event retry tracking (max 1 retry for critical events like SOS)
EVENT_RETRY_TIMEOUT = 3000  # Retry after 3 seconds if no ACK
_pending_event_acks = {}  # {msg_id: {"msg": data, "sent_at": timestamp, "retry_count": 0}}

_esp_now = None
_initialized = False
_wifi = None
_last_init_attempt = 0


def _get_actuator_status_string(msg_type="data", msg_id=None, reply_to_id=None):
    """Format all actuator states into a JSON message.
    
    Args:
        msg_type: Type of message - 'data' (periodic), 'event' (immediate), 'ack' (confirmation)
        msg_id: Message ID (auto-generated if None)
        reply_to_id: ID of message this is replying to (for ACKs)
    """
    global _next_msg_id
    if msg_id is None:
        msg_id = _next_msg_id
        _next_msg_id += 1
    
    modes = state.actuator_state["led_modes"]
    
    # Sanitize LCD strings to prevent JSON corruption
    def sanitize_lcd_text(text, max_len=16):
        """Clean LCD text for safe JSON serialization."""
        if not text:
            return ""
        text = str(text)
        text = text[:max_len]
        # Remove potentially problematic characters for JSON
        text = "".join(c for c in text if ord(c) >= 32 and ord(c) < 127 or c in '\n\t')
        return text
    
    # Get actuator values
    led_green = modes.get("green", "off")
    led_blue = modes.get("blue", "off")
    led_red = modes.get("red", "off")
    servo_angle = state.actuator_state["servo"].get("angle")
    lcd_line1 = sanitize_lcd_text(state.actuator_state["lcd"].get("line1", ""))
    lcd_line2 = sanitize_lcd_text(state.actuator_state["lcd"].get("line2", ""))
    buzzer_active = state.actuator_state["buzzer"].get("active", False)
    audio_playing = state.actuator_state["audio"].get("playing", False)
    sos_mode = state.actuator_state.get("sos_mode", False)
    
    # Manual JSON construction to guarantee field order (MicroPython ujson compatibility)
    # Using list + join() for efficiency (string concatenation in loop is very slow in MicroPython)
    
    parts = [
        "{\"v\":", str(config.FIRMWARE_VERSION), ",",
        "\"t\":\"", msg_type, "\",",
        "\"id\":", str(msg_id), ",",
        "\"ts\":", str(ticks_ms()), ",",
        "\"L\":{",
        "\"g\":\"", led_green, "\",",
        "\"b\":\"", led_blue, "\",",
        "\"r\":\"", led_red, "\"",
        "},",
        "\"S\":{",
        "\"a\":", ("null" if servo_angle is None else str(servo_angle)),
        "},",
        "\"D\":{",
        "\"1\":\"", lcd_line1, "\",",
        "\"2\":\"", lcd_line2, "\"",
        "},",
        "\"B\":\"", ("ON" if buzzer_active else "OFF"), "\",",
        "\"A\":\"", ("PLAY" if audio_playing else "STOP"), "\",",
        "\"O\":", ("true" if sos_mode else "false"),
    ]
    
    if reply_to_id is not None:
        parts.append(",\"r\":")
        parts.append(str(reply_to_id))
    
    parts.append("}")
    json_str = "".join(parts)
    msg_bytes = json_str.encode("utf-8")
    
    # CRITICAL FIX: Pad to 250 bytes with null terminators
    # ESP-NOW may add garbage padding, but we control it here
    # This ensures Board A can safely strip null bytes without losing data
    if len(msg_bytes) < 250:
        msg_bytes = msg_bytes + b'\x00' * (250 - len(msg_bytes))
    
    # Check ESP-NOW size limit (250 bytes max)
    if len(msg_bytes) > 250:
        log("communication.espnow", "WARNING: Message too large ({} bytes, max 250). May be truncated!".format(len(msg_bytes)))
    
    # Validate JSON is correct and parseable
    try:
        json.loads(json_str)  # Verify JSON is valid
    except ValueError as e:
        log("communication.espnow", "WARNING: Generated JSON is invalid: {}".format(e))
        log("communication.espnow", "JSON: {}".format(json_str[:100]))
        return msg_bytes
    except Exception as e:
        log("communication.espnow", "ERROR serializing to JSON: {}".format(e))
        # Fallback: send minimal valid JSON
        fallback = json.dumps({"v": config.FIRMWARE_VERSION, "t": msg_type, "id": msg_id, "ts": ticks_ms()}).encode("utf-8")
        log("communication.espnow", "Using fallback message")
        return fallback
    
    return msg_bytes


def init_espnow_comm():
    """Initialize ESP-NOW on Scheda B (Server mode).
    
    Server waits for connections from Scheda A (client).
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
        
        # FIX: Set fixed WiFi channel to avoid interference and channel hopping
        # MUST match Board A's channel (1)
        try:
            _wifi.config(channel=1)
            log("communication.espnow", "WiFi channel fixed to 1")
        except:
            log("communication.espnow", "Could not set WiFi channel (not critical)")
        
        # FIX: Increase TX power to maximum for better reliability
        try:
            _wifi.config(txpower=20)  # 20 dBm = max power
            log("communication.espnow", "TX power set to maximum")
        except:
            pass  # Some ESP32 versions don't support this
        
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
        
        # Log after successful send with full context
        _esp_now.send(MAC_A, data)
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


def send_event_immediate(event_type="sos_activated", custom_data=None):
    """Send an immediate event to Board A, bypassing the normal timer.
    
    Used for urgent notifications like SOS activation, emergency states, etc.
    
    Args:
        event_type: Type of event ('sos_activated', 'emergency', etc.)
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
    log("espnow_b", "Event queued: {}".format(event_type))
    return True


def _parse_command(msg_bytes):
    """Parse and execute command received via ESP-NOW.
    
    Command format (from Board A forwarding app/Node-RED commands):
    {"target": "B", "command": "servo", "args": [180], "_source": "app", "_session_id": "..."}
    
    Returns:
        True if this was a command (parsed and executed)
        False if not a command (should try parsing as sensor data)
        None if parsing failed (don't try further parsing)
    """
    try:
        msg_str = msg_bytes.decode("utf-8")
        data = json.loads(msg_str)
        
        # Check if this is a command (has target, command, args keys)
        if "target" in data and "command" in data:
            target = data.get("target", "").upper()
            
            # Ignore if not for us
            if target != "B":
                return None  # Parsing succeeded but not for us, don't try sensor parsing
            
            command = data.get("command", "")
            args = data.get("args", [])
            source = data.get("_source", "unknown")
            session_id = data.get("_session_id", "")
            
            log("communication.espnow", "CMD RX from A: cmd={} args={} source={} session={}".format(
                command, args, source, session_id
            ))
            
            # Execute command using command_handler
            try:
                from communication import command_handler
                response = command_handler.handle_command(command, args)
                
                if response.get("success"):
                    log("communication.espnow", "CMD OK: {}".format(response.get("message")))
                else:
                    log("communication.espnow", "CMD ERROR: {}".format(response.get("message")))
            except Exception as e:
                log("communication.espnow", "CMD execution error: {}".format(e))
            
            return True  # This was a command
        
        return False  # Not a command, could be sensor data
        
    except Exception as e:
        # JSON parsing failed or decode error - log and return None to prevent further attempts
        log("communication.espnow", "Parse error: {}".format(e))
        return None  # Signal that parsing failed completely


def _validate_message(msg_bytes):
    """Validate message structure before JSON parsing.
    
    Returns:
        True if message looks valid, False otherwise
    """
    # Check type
    if not isinstance(msg_bytes, (bytes, bytearray)):
        log("espnow_b", "Invalid message type: {}".format(type(msg_bytes)))
        return False
    
    # Check not empty
    if len(msg_bytes) == 0:
        log("espnow_b", "Empty message received")
        return False
    
    # Strip null bytes first
    msg_bytes = bytes(msg_bytes).rstrip(b'\x00')
    
    # Check if it starts with '{' (JSON)
    if msg_bytes[0:1] != b'{':
        log("espnow_b", "Message doesn't start with '{{': preview={}".format(msg_bytes[:20]))
        return False
    
    # Check if it ends with '}'
    if msg_bytes[-1:] != b'}':
        log("espnow_b", "Message doesn't end with '}}': preview={}".format(msg_bytes[-20:]))
        return False
    
    # Basic UTF-8 validation
    try:
        msg_bytes.decode("utf-8")
    except UnicodeDecodeError:
        log("espnow_b", "Message is not valid UTF-8")
        return False
    
    return True


def _parse_sensor_state(msg_bytes):
    """Parse received sensor state from Board A (JSON format) and update state.
    
    Supports both compact and full JSON formats:
    
    Compact format only (v=version, t=type, id=msg_id, etc.):
    {"v":1,"t":"data","id":1,"ts":9622,"s":{"T":25,"C":150,"U":50,"P":false,"H":{"b":75,"o":98}},"B":{"1":false,"2":false,"3":false},"A":{"L":"normal","S":null}}
    """
    try:
        # Validate message structure first
        if not _validate_message(msg_bytes):
            return None
        
        # Strip trailing null bytes that ESP-NOW may add
        msg_bytes = msg_bytes.rstrip(b'\x00')
        
        msg_str = msg_bytes.decode("utf-8")
        
        # Try to parse JSON
        try:
            data = json.loads(msg_str)
        except ValueError as e:
            log("communication.espnow", "Parse error: " + str(e))
            log("communication.espnow", "Message length: " + str(len(msg_str)))
            log("communication.espnow", "First 100 chars: " + msg_str[:100])
            log("communication.espnow", "Last 50 chars: " + msg_str[-50:])
            return None
        
        # Extract message metadata (compact format only)
        msg_id = data.get("id", 0)
        msg_type = data.get("t", "data")
        remote_version = data.get("v")
        
        log("espnow_b", "RX: msg_id={} type={}".format(msg_id, msg_type))
        
        # Track received message ID to prevent duplicates
        global _last_received_msg_id
        if msg_id <= _last_received_msg_id and msg_type != "ack":
            log("espnow_b", "Duplicate msg_id={}, ignoring".format(msg_id))
            return None  # Return msg_id None to signal duplicate
        if msg_type != "ack":
            _last_received_msg_id = msg_id
        
        # If this is just an ACK, don't update state and DON'T send another ACK back
        if msg_type == "ack":
            reply_to = data.get("r")
            log("espnow_b", "ACK received for msg_id={}".format(reply_to))
            
            # Remove from pending events if it was an event waiting for ACK
            global _pending_event_acks
            if reply_to in _pending_event_acks:
                del _pending_event_acks[reply_to]
                log("espnow_b", "Event msg_id={} confirmed, removed from pending".format(reply_to))
            
            return -1  # Special code: ACK received, don't respond with another ACK
        
        # Check version (warning only, don't block communication)
        if remote_version != config.FIRMWARE_VERSION:
            log("communication.espnow", "WARNING: Firmware version mismatch! Local=v{}, Remote=v{}".format(
                config.FIRMWARE_VERSION, remote_version
            ))
        
        # Parse sensors (compact format only)
        sensors = data.get("s", {})
        state.received_sensor_state["temperature"] = sensors.get("T")
        state.received_sensor_state["co"] = sensors.get("C")
        state.received_sensor_state["ultrasonic_distance"] = sensors.get("U")
        state.received_sensor_state["presence_detected"] = sensors.get("P", False)
        
        # Parse heart rate (compact)
        hr = sensors.get("H", {})
        state.received_sensor_state["heart_rate_bpm"] = hr.get("b")
        state.received_sensor_state["heart_rate_spo2"] = hr.get("o")
        
        # Parse buttons (compact)
        buttons = data.get("B", {})
        state.received_sensor_state["button_b1"] = buttons.get("1", False)
        state.received_sensor_state["button_b2"] = buttons.get("2", False)
        state.received_sensor_state["button_b3"] = buttons.get("3", False)
        
        # Parse alarm (compact)
        alarm = data.get("A", {})
        state.received_sensor_state["alarm_level"] = alarm.get("L", "normal")
        state.received_sensor_state["alarm_source"] = alarm.get("S")
        state.received_sensor_state["alarm_sos_mode"] = alarm.get("M", False)
        
        state.received_sensor_state["last_update"] = ticks_ms()
        state.received_sensor_state["is_stale"] = False
        
        return msg_id  # Return msg_id to send ACK
    except Exception as e:
        # Silent failure - handle parse errors without verbose logging
        pass
        return None


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
    
    # Check if A is still connected (heartbeat timeout check)
    now = ticks_ms()
    if _last_message_from_a > 0:
        elapsed_since = ticks_diff(now, _last_message_from_a)
        if elapsed_since > CONNECTION_TIMEOUT:
            if _a_is_connected:
                log("communication.espnow", "WARNING: Board A disconnected (no message for 10s)")
                _a_is_connected = False
                # Reset msg_id counter for re-sync when A reconnects
                global _last_received_msg_id
                _last_received_msg_id = 0
                log("communication.espnow", "Reset message ID counter for re-sync")
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
    
    # Drain ALL pending messages from buffer to prevent overflow
    # Process messages in order, use first valid one
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
            
            # Convert to bytes if it's a bytearray
            if isinstance(msg, bytearray):
                msg = bytes(msg)
            
            log("espnow_b", "RX from {} len={}".format(mac_str, len(msg)))
            
            # Validate message before storing
            if _validate_message(msg):
                valid_messages.append(msg)
            else:
                log("espnow_b", "Message validation failed, skipping")
            
        except OSError:
            # OSError is normal when buffer is empty - silent break
            break
    
    # Process the FIRST valid message (most likely to be complete)
    if valid_messages:
        if messages_processed > 1:
            log("espnow_b", "Drained {} messages ({} valid), using first valid".format(
                messages_processed, len(valid_messages)))
        
        # Use first valid message
        msg_to_process = valid_messages[0]
        
        try:
            # First, try to parse as a command (from app via A)
            # Returns: True (command), False (not command), None (parsing failed)
            cmd_result = _parse_command(msg_to_process)
            
            # If it was a command, update connection status
            if cmd_result is True:
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
            
            # If not a command (False), try parsing as sensor data
            elif cmd_result is False:
                # Parse JSON sensor data from A (returns msg_id, -1 for ACK, or None for error)
                received_msg_id = _parse_sensor_state(msg_to_process)
                
                # Send ACK only if we successfully parsed a data or event message
                # Don't send ACK for ACKs (received_msg_id == -1)
                if received_msg_id is not None and received_msg_id > 0:
                    _last_message_from_a = ticks_ms()
                    _messages_received += 1
                    if not _a_is_connected:
                        log("communication.espnow", "Board A connected")
                        _a_is_connected = True
                    # Inform actuator loop (updates LED state)
                    try:
                        from core import actuator_loop
                        actuator_loop.set_espnow_connected(True)
                    except Exception:
                        pass
                    
                    # Send ACK back to A (confirmation of receipt)
                    ack_msg = _get_actuator_status_string(msg_type="ack", reply_to_id=received_msg_id)
                    send_message(ack_msg)
                    log("espnow_b", "Sent ACK for msg_id={}".format(received_msg_id))
            
            # If cmd_result is None, parsing completely failed, error already logged
                    
        except Exception as e:
            log("communication.espnow", "Message processing error: {}".format(e))
    
    # Check for events that need retry (no ACK received within timeout)
    _check_event_retry()
    
    # Send pending events immediately (bypass timer)
    try:
        global _pending_events, _pending_event_acks
        if _pending_events:
            event = _pending_events.pop(0)
            
            # Get message ID for tracking
            msg_id = _next_msg_id
            event_msg = _get_actuator_status_string(msg_type="event", msg_id=msg_id)
            
            # Track this event for ACK confirmation (max 1 retry)
            _pending_event_acks[msg_id] = {
                "msg": event_msg,
                "sent_at": ticks_ms(),
                "retry_count": 0
            }
            
            send_message(event_msg)
    except Exception as e:
        log("communication.espnow", "Event send error: {}".format(e))

