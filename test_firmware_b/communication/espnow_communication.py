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

# Connection tracking and message IDs
CONNECTION_TIMEOUT = 10000  # Consider A disconnected if no message for 10 seconds (4x send interval)
REINIT_INTERVAL = 5000      # Try to recover ESP-NOW every 5 seconds when down
_last_message_from_a = 0
_a_is_connected = False
_version_mismatch_logged = False  # Prevent log spam
_messages_received = 0
_state_log_interval = None  # Disabled snapshots

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
        fallback = json.dumps({"v": 1, "t": msg_type, "id": msg_id, "ts": ticks_ms()}).encode("utf-8")
        log("communication.espnow", "Using fallback message")
        return fallback


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
                log("espnow_b", "Event msg_id={} timeout, retrying (attempt 2/2)".format(msg_id))
                send_message(event_info["msg"])
                event_info["sent_at"] = now
                event_info["retry_count"] += 1
            else:
                # Max retry reached, give up
                log("espnow_b", "Event msg_id={} failed after 1 retry, giving up".format(msg_id))
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
    {"target": "B", "command": "servo", "args": [90], "_source": "app", "_session_id": "..."}
    
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
                log("espnow_b", "Command not for us (target={})".format(target))
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


def _parse_sensor_state(msg_bytes):
    """Parse received sensor state from Board A (JSON format) and update state.
    
    Supports both compact and full JSON formats:
    
    Compact format (v=version, t=type, id=msg_id, etc.):
    {"v":1,"t":"data","id":1,"ts":9622,"s":{"T":25,"C":150,"U":50,"P":false,"H":{"b":75,"o":98}},"B":{"1":false,"2":false,"3":false},"A":{"L":"normal","S":null}}
    
    Full format (for backward compatibility):
    {"version":1,"msg_type":"data","msg_id":1,"timestamp":12345,"sensors":{"temperature":25,"co":150,...},"buttons":{"b1":false,...},"alarm":{"level":"normal",...}}
    """
    try:
        msg_str = msg_bytes.decode("utf-8")
        log("espnow_b", "RX Parse: msg_str length={} first_100={}".format(len(msg_str), msg_str[:100]))
        
        # Pre-validation: check message integrity
        if not msg_str.strip():
            log("espnow_b", "ERROR: Empty message received")
            return None
        if not msg_str.startswith('{'):
            log("espnow_b", "ERROR: Message doesn't start with '{{' - corrupted!")
            log("espnow_b", "First 50 chars: {}".format(msg_str[:50]))
            return None
        if not msg_str.endswith('}'):
            log("espnow_b", "ERROR: Message doesn't end with '}}' - likely truncated!")
            log("espnow_b", "Last 50 chars: {}".format(msg_str[-50:]))
            return None
        
        # Detect if message might be two JSON objects concatenated (common bug)
        brace_count = msg_str.count('{')
        if brace_count > 1:
            log("espnow_b", "WARNING: Multiple JSON objects detected in single message ({}x '{')".format(brace_count))
            log("espnow_b", "Message might be corrupted or contain multiple concatenated messages")
            # Try to extract the first valid JSON object
            try:
                # Find the first complete JSON object
                bracket_count = 0
                for i, char in enumerate(msg_str):
                    if char == '{':
                        bracket_count += 1
                    elif char == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            # Found first complete object
                            first_json = msg_str[:i+1]
                            log("espnow_b", "Extracted first JSON object: {}".format(first_json[:80]))
                            msg_str = first_json
                            break
            except Exception as e:
                log("espnow_b", "Failed to extract first JSON object: {}".format(e))
        
        # Try to parse JSON
        try:
            data = json.loads(msg_str)
        except ValueError as e:
            # JSON parsing failed - show COMPLETE message for debugging (no truncation)
            log("espnow_b", "RX Parse FAILED: {}".format(e))
            log("espnow_b", "Message length: {} bytes".format(len(msg_str)))
            log("espnow_b", "FULL message: {}".format(msg_str))
            # Check for common issues
            if not msg_str.endswith('}'):
                log("espnow_b", "ERROR: Message doesn't end with '}}' - likely truncated!")
                log("espnow_b", "Last 20 chars: {}".format(msg_str[-20:]))
            return None
        
        # Detect format (compact uses 'v', full uses 'version')
        is_compact = "v" in data
        
        # Extract message metadata (support both formats)
        if is_compact:
            msg_id = data.get("id", 0)
            msg_type = data.get("t", "data")
            remote_version = data.get("v")
        else:
            msg_id = data.get("msg_id", 0)
            msg_type = data.get("msg_type", "data")
            remote_version = data.get("version")
        
        log("espnow_b", "RX OK: msg_id={} type={} fmt={}".format(msg_id, msg_type, "compact" if is_compact else "full"))
        
        # Track received message ID to prevent duplicates
        global _last_received_msg_id
        if msg_id <= _last_received_msg_id and msg_type != "ack":
            log("espnow_b", "Duplicate msg_id={}, ignoring".format(msg_id))
            return None  # Return msg_id None to signal duplicate
        if msg_type != "ack":
            _last_received_msg_id = msg_id
        
        # If this is just an ACK, don't update state, just return msg_id
        if msg_type == "ack":
            reply_to = data.get("r" if is_compact else "reply_to_id")
            log("espnow_b", "ACK received for msg_id={}".format(reply_to))
            
            # Remove from pending events if it was an event waiting for ACK
            global _pending_event_acks
            if reply_to in _pending_event_acks:
                del _pending_event_acks[reply_to]
                log("espnow_b", "Event msg_id={} confirmed, removed from pending".format(reply_to))
            
            return msg_id  # Return to signal ACK processed
        
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
        
        # Parse sensors (support both formats)
        if is_compact:
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
        else:
            # Full format (backward compatibility)
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
        
        log("communication.espnow", "Sensor data received (v{}) msg_id={} type={} - Temp={}, CO={}, Alarm={}".format(
            remote_version,
            msg_id,
            msg_type,
            state.received_sensor_state["temperature"],
            state.received_sensor_state["co"],
            state.received_sensor_state["alarm_level"]
        ))
        log("espnow_b", "RX OK - Sensor state updated")
        return msg_id  # Return msg_id to send ACK
    except Exception as e:
        log("communication.espnow", "Parse error: {}".format(e))
        log("espnow_b", "RX Parse FAILED: {}".format(e))
        return None


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
    
    # Check if A is still connected (heartbeat timeout check)
    now = ticks_ms()
    if _last_message_from_a > 0:
        elapsed_since = ticks_diff(now, _last_message_from_a)
        if elapsed_since > CONNECTION_TIMEOUT:
            if _a_is_connected:
                log("communication.espnow", "WARNING: Board A disconnected (no message for 10s)")
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
    
    # Drain ALL pending messages from buffer to prevent overflow
    # Read up to 10 messages per update cycle
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
            
            # Convert to bytes if it's a bytearray
            if isinstance(msg, bytearray):
                msg = bytes(msg)
            
            # Debug: show received payload with first AND last chars
            preview_start = msg[:60]
            preview_end = msg[-30:] if len(msg) > 60 else b""
            log("espnow_b", "RX from {} len={} start={} end={}".format(mac_str, len(msg), preview_start, preview_end))
            
        except OSError:
            # OSError is normal when buffer is empty - silent break
            break
    
    # Process only the LAST received message (most recent data)
    if last_valid_msg is not None:
        if messages_processed > 1:
            log("espnow_b", "Drained {} messages, using latest".format(messages_processed))
        
        try:
            # First, try to parse as a command (from app via A)
            # Returns: True (command), False (not command), None (parsing failed)
            cmd_result = _parse_command(last_valid_msg)
            
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
                # Parse JSON sensor data from A (returns msg_id or None)
                received_msg_id = _parse_sensor_state(last_valid_msg)
                
                # Send ACK only if we successfully parsed a data or event message
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
            log("espnow_b", "Sending event: {}".format(event.get("event_type")))
            
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
    
    # Log complete state every 15 seconds
    if _state_log_interval and elapsed("espnow_state_log", _state_log_interval):
        try:
            _log_complete_state()
        except Exception as e:
            log("communication.espnow", "Log state error: {}".format(e))

