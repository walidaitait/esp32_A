"""MQTT bridge to Node-RED and mobile app via Adafruit IO.

Imported by: main.py
Imports: umqtt.simple, ujson, time, core.timers, core.wifi, core.state, 
         debug.debug, config.config, config.wifi_config

Board A acts as the sole northbound gateway:
- Publishes sensor data + alarm state to Node-RED
- Publishes Board B actuator state (forwarded from ESP-NOW)
- Receives commands from Node-RED/mobile app
- Forwards commands to Board B via ESP-NOW when target="B"

Non-blocking design: All operations in update() using elapsed() timers.
If disabled or MQTT unavailable, module stays inert without impacting firmware.
"""

from time import ticks_ms, ticks_diff  # type: ignore
from core.timers import elapsed
from core import wifi, state
from debug.debug import log
from config import config
from config.wifi_config import ADA_USERNAME, ADA_KEY

try:
    import ujson as json  # type: ignore
except ImportError:
    import json  # type: ignore

try:
    from umqtt.simple import MQTTClient  # type: ignore
except ImportError:
    MQTTClient = None  # type: ignore

_client = None
_enabled = False
_connected = False
_last_connect_attempt = 0
_RECONNECT_INTERVAL_MS = 5000
_command_queue = []
_publish_requested = False  # set True to force an immediate state publish on next update()

STATE_INTERVAL_MS = getattr(config, "NODERED_STATE_INTERVAL_MS", 3000)


def _topic(feed_key):
    feeds = getattr(config, "NODERED_FEEDS", {}) or {}
    feed = feeds.get(feed_key, "")
    if not feed or not ADA_USERNAME:
        return None
    # Adafruit IO topic format: <username>/feeds/<feed>
    return "{}/feeds/{}".format(ADA_USERNAME, feed)


def _on_message(topic, msg):
    """Queue incoming command messages for later handling.
    
    Expects JSON conforming to APP_PROTOCOL_SCHEMA:
    {
        "msg_type": "command",
        "timestamp_ms": <int>,
        "command": "sos_activate" | "sos_deactivate" | "gate_open" | "gate_close" | "query",
        "session_id": <string>,
        "params": {}
    }
    """
    try:
        topic_str = topic.decode() if isinstance(topic, (bytes, bytearray)) else str(topic)
        payload_str = msg.decode() if isinstance(msg, (bytes, bytearray)) else str(msg)
        try:
            payload = json.loads(payload_str)
        except Exception:
            log("nodered", "CMD RX JSON parse failed for topic={}".format(topic_str))
            return
        
        # Validate protocol compliance
        if not isinstance(payload, dict):
            log("nodered", "CMD RX payload not dict: topic={}".format(topic_str))
            return
            
        msg_type = payload.get("msg_type")
        if msg_type != "command":
            log("nodered", "CMD RX invalid msg_type={}: topic={}".format(msg_type, topic_str))
            return
        
        command = payload.get("command")
        if command not in ["sos_activate", "sos_deactivate", "gate_open", "gate_close", "query"]:
            log("nodered", "CMD RX unknown command={}: topic={}".format(command, topic_str))
            return
        
        # Valid command, queue it
        _command_queue.append({"topic": topic_str, "payload": payload})
        log("nodered", "CMD RX valid: cmd={} session_id={}".format(command, payload.get("session_id")))
    except Exception as e:
        log("nodered", "CMD parse error: {}".format(e))


def _connect_mqtt():
    global _client, _connected, _last_connect_attempt

    _last_connect_attempt = ticks_ms()

    if MQTTClient is None:
        log("nodered", "MQTT client library not available")
        return False

    if not wifi.is_connected():
        log("nodered", "WiFi not connected, skip MQTT connect")
        return False

    try:
        client = MQTTClient(
            client_id=getattr(config, "NODERED_CLIENT_ID", "esp32a"),
            server=getattr(config, "NODERED_BROKER", "io.adafruit.com"),
            port=getattr(config, "NODERED_PORT", 1883),
            user=ADA_USERNAME or None,
            password=ADA_KEY or None,
            keepalive=getattr(config, "NODERED_KEEPALIVE", 60),
            ssl=getattr(config, "NODERED_USE_TLS", False),
            ssl_params={"server_hostname": getattr(config, "NODERED_BROKER", "io.adafruit.com")}
            if getattr(config, "NODERED_USE_TLS", False) else None,
        )
        client.set_callback(_on_message)
        client.connect()

        # Subscribe to command feed if configured
        cmd_topic = _topic("command")
        if cmd_topic:
            client.subscribe(cmd_topic, qos=getattr(config, "NODERED_QOS", 0))
            log("nodered", "Subscribed to command feed: {}".format(cmd_topic))
        else:
            log("nodered", "Command feed not configured; subscriptions skipped")

        _client = client
        _connected = True
        log("nodered", "MQTT connected to {}:{}".format(
            getattr(config, "NODERED_BROKER", "io.adafruit.com"), getattr(config, "NODERED_PORT", 1883)
        ))
        return True
    except Exception as e:
        log("nodered", "MQTT connect failed: {}".format(e))
        _client = None
        _connected = False
        return False


def init():
    """Initialize Node-RED/Adafruit bridge (non-blocking if disabled)."""
    global _enabled, _connected
    _enabled = getattr(config, "NODERED_ENABLED", False)

    if not _enabled:
        log("nodered", "Bridge disabled by config")
        return False

    if _connect_mqtt():
        return True

    # Do not raise: update() will retry later
    return False


def _publish(feed_key, payload):
    if not _enabled or not _connected or _client is None:
        return False

    topic = _topic(feed_key)
    if not topic:
        return False

    try:
        msg = json.dumps(payload)
        _client.publish(topic, msg, qos=getattr(config, "NODERED_QOS", 0))
        log("nodered", "TX {} -> {}".format(feed_key, topic))
        return True
    except Exception as e:
        log("nodered", "Publish error ({}): {}".format(feed_key, e))
        return False


def _build_state_payload():
    """Build state payload conforming to APP_PROTOCOL_SCHEMA sensor_data message.
    
    Schema:
    {
        "msg_type": "sensor_data",
        "timestamp_ms": <int>,
        "sensors": {
            "temperature_c": <number | null>,
            "co_ppm": <integer | null>,
            "heart_rate_bpm": <integer | null>,
            "spo2_percent": <integer | null>,
            "ultrasonic_distance_cm": <number | null>,
            "ultrasonic_presence": <boolean>
        },
        "alarm": {
            "level": "normal" | "warning" | "danger",
            "source": "co" | "temperature" | "heart_rate" | "manual" | null,
            "sos_mode": <boolean>
        },
        "system": {
            "wifi_connected": <boolean>,
            "firmware_version": <integer>,
            "gate_open": <boolean>
        }
    }
    """
    # Extract heart rate data safely
    hr_data = state.sensor_data.get("heart_rate", {})
    heart_rate_bpm = hr_data.get("bpm") if isinstance(hr_data, dict) else None
    spo2_percent = hr_data.get("spo2") if isinstance(hr_data, dict) else None
    
    return {
        "msg_type": "sensor_data",
        "timestamp_ms": ticks_ms(),
        "sensors": {
            "temperature_c": state.sensor_data.get("temperature"),
            "co_ppm": state.sensor_data.get("co"),
            "heart_rate_bpm": heart_rate_bpm,
            "spo2_percent": spo2_percent,
            "ultrasonic_distance_cm": state.sensor_data.get("ultrasonic_distance_cm"),
            "ultrasonic_presence": state.sensor_data.get("ultrasonic_presence", False),
        },
        "alarm": {
            "level": state.alarm_state.get("level", "normal"),
            "source": state.alarm_state.get("source"),
            "sos_mode": state.alarm_state.get("sos_mode", False),
        },
        "system": {
            "wifi_connected": state.wifi.is_connected() if hasattr(state, "wifi") else True,
            "firmware_version": getattr(config, "FIRMWARE_VERSION", 1),
            "gate_open": state.gate_state.get("gate_open", False),
        },
    }


def publish_state_snapshot():
    """Publish current state snapshot to state feed (if configured)."""
    return _publish("state", _build_state_payload())


def publish_state_now():
    """Immediate state publish (bypasses timer, for urgent events)."""
    return publish_state_snapshot()


def request_publish_now():
    """Request an immediate publish to be performed in update() (non-blocking)."""
    global _publish_requested
    _publish_requested = True


def publish_event(event_payload):
    """Publish an event dictionary to the event feed (if configured)."""
    return _publish("event", event_payload)


def get_next_command():
    """Pop next queued command (or None).
    
    Returns a dict with:
    - topic: MQTT topic where command came from
    - payload: Full command payload dict (already validated by _on_message)
    """
    if _command_queue:
        return _command_queue.pop(0)
    return None


def _process_app_command(cmd_payload):
    """Process an incoming app command from the protocol.
    
    Maps app commands to internal ESP32-A operations:
    - sos_activate -> alarm trigger
    - sos_deactivate -> alarm clear
    - gate_open -> forward to ESP32-B via ESPNow
    - gate_close -> forward to ESP32-B via ESPNow
    - query -> immediate state publish
    
    Returns:
        dict with 'success' (bool) and 'message' (string)
    """
    from communication import espnow_communication
    
    command = cmd_payload.get("command", "")
    session_id = cmd_payload.get("session_id", "unknown")
    
    try:
        if command == "sos_activate":
            # Trigger emergency alarm
            state.alarm_state["level"] = "danger"
            state.alarm_state["source"] = "manual"
            state.alarm_state["sos_mode"] = True
            # Publish immediately
            publish_state_now()
            log("nodered", "CMD: SOS activate from {}".format(session_id))
            return {"success": True, "message": "SOS activated"}
        
        elif command == "sos_deactivate":
            # Clear alarm
            state.alarm_state["level"] = "normal"
            state.alarm_state["source"] = None
            state.alarm_state["sos_mode"] = False
            # Publish immediately
            publish_state_now()
            log("nodered", "CMD: SOS deactivate from {}".format(session_id))
            return {"success": True, "message": "SOS deactivated"}
        
        elif command == "gate_open":
            # Forward gate open command to ESP32-B via ESPNow
            # Gate open = servo at 90 degrees
            espnow_command = {
                "target": "B",
                "command": "servo",
                "args": [90],
                "_source": "app",
                "_session_id": session_id
            }
            if espnow_communication.send_command(espnow_command):
                # Update local gate state to maintain sync with app
                state.gate_state["gate_open"] = True
                # Publish immediately to confirm state change to app
                publish_state_now()
                log("nodered", "CMD: Gate open forwarded to B from {}".format(session_id))
                return {"success": True, "message": "Gate open command sent to B"}
            else:
                log("nodered", "CMD: Gate open forward failed from {}".format(session_id))
                return {"success": False, "message": "Failed to forward gate open to B"}
        
        elif command == "gate_close":
            # Forward gate close command to ESP32-B via ESPNow
            # Gate close = servo at 0 degrees
            espnow_command = {
                "target": "B",
                "command": "servo",
                "args": [0],
                "_source": "app",
                "_session_id": session_id
            }
            if espnow_communication.send_command(espnow_command):
                # Update local gate state to maintain sync with app
                state.gate_state["gate_open"] = False
                # Publish immediately to confirm state change to app
                publish_state_now()
                log("nodered", "CMD: Gate close forwarded to B from {}".format(session_id))
                return {"success": True, "message": "Gate close command sent to B"}
            else:
                log("nodered", "CMD: Gate close forward failed from {}".format(session_id))
                return {"success": False, "message": "Failed to forward gate close to B"}
        
        elif command == "query":
            # Publish current state immediately
            publish_state_now()
            log("nodered", "CMD: Query from {}".format(session_id))
            return {"success": True, "message": "State published"}
        
        else:
            log("nodered", "CMD: Unknown command {} from {}".format(command, session_id))
            return {"success": False, "message": "Unknown command: {}".format(command)}
    
    except Exception as e:
        log("nodered", "CMD process error: {}".format(e))
        return {"success": False, "message": "Error processing command: {}".format(e)}


def process_commands():
    """Process all queued commands from MQTT.
    
    Should be called from main loop to handle commands received from app.
    """
    while True:
        cmd = get_next_command()
        if not cmd:
            break
        
        try:
            payload = cmd.get("payload", {})
            if payload.get("msg_type") == "command":
                _process_app_command(payload)
            else:
                log("nodered", "Unexpected payload msg_type: {}".format(payload.get("msg_type")))
        except Exception as e:
            log("nodered", "Error processing queued command: {}".format(e))


def update():
    """Non-blocking update: reconnect if needed, handle messages, process commands, auto-publish."""
    global _connected, _client
    global _publish_requested

    if not _enabled:
        return

    # Reconnect if disconnected, throttled
    now = ticks_ms()
    if (not _connected) and (ticks_diff(now, _last_connect_attempt) > _RECONNECT_INTERVAL_MS):
        _connect_mqtt()

    if not _connected or _client is None:
        return

    # Pump incoming messages (adds to queue via _on_message callback)
    try:
        _client.check_msg()
    except Exception as e:
        log("nodered", "MQTT check_msg failed: {}".format(e))
        _connected = False
        _client = None
        return

    # Process any queued commands from app (converted to internal operations)
    process_commands()

    # Fast-path publish requested by alarm logic
    if _publish_requested:
        _publish_requested = False
        publish_state_snapshot()

    # Periodic state publish
    if elapsed("nodered_state_pub", STATE_INTERVAL_MS):
        publish_state_snapshot()


# End of nodered_client
