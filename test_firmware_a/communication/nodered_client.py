"""Node-RED / Adafruit MQTT bridge for Board A.

Board A acts as the sole northbound bridge: it publishes local/B state to
Node-RED (via the configured MQTT broker, e.g., Adafruit IO) and receives
commands that may target A or be forwarded to B.

Non-blocking design: all work happens in update() using elapsed() timers.
If disabled or MQTT is unavailable, the module stays inert without
impacting the rest of the firmware.
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

STATE_INTERVAL_MS = getattr(config, "NODERED_STATE_INTERVAL_MS", 3000)


def _topic(feed_key):
    feeds = getattr(config, "NODERED_FEEDS", {}) or {}
    feed = feeds.get(feed_key, "")
    if not feed or not ADA_USERNAME:
        return None
    # Adafruit IO topic format: <username>/feeds/<feed>
    return "{}/feeds/{}".format(ADA_USERNAME, feed)


def _on_message(topic, msg):
    """Queue incoming command messages for later handling."""
    try:
        topic_str = topic.decode() if isinstance(topic, (bytes, bytearray)) else str(topic)
        payload_str = msg.decode() if isinstance(msg, (bytes, bytearray)) else str(msg)
        try:
            payload = json.loads(payload_str)
        except Exception:
            payload = {"raw": payload_str}
        _command_queue.append({"topic": topic_str, "payload": payload})
        log("nodered", "CMD RX topic={} payload={}".format(topic_str, str(payload)[:80]))
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
    return {
        "src": "a",
        "ts": ticks_ms(),
        "sensors": state.sensor_data,
        "alarm": state.alarm_state,
        "buttons": state.button_state,
        "b_state": state.received_actuator_state,
    }


def publish_state_snapshot():
    """Publish current state snapshot to state feed (if configured)."""
    return _publish("state", _build_state_payload())


def publish_state_now():
    """Immediate state publish (bypasses timer, for urgent events)."""
    return publish_state_snapshot()


def publish_event(event_payload):
    """Publish an event dictionary to the event feed (if configured)."""
    return _publish("event", event_payload)


def get_next_command():
    """Pop next queued command (or None)."""
    if _command_queue:
        return _command_queue.pop(0)
    return None


def update():
    """Non-blocking update: reconnect if needed, handle messages, auto-publish."""
    global _connected, _client

    if not _enabled:
        return

    # Reconnect if disconnected, throttled
    now = ticks_ms()
    if (not _connected) and (ticks_diff(now, _last_connect_attempt) > _RECONNECT_INTERVAL_MS):
        _connect_mqtt()

    if not _connected or _client is None:
        return

    # Pump incoming messages
    try:
        _client.check_msg()
    except Exception as e:
        log("nodered", "MQTT check_msg failed: {}".format(e))
        _connected = False
        _client = None
        return

    # Periodic state publish
    if elapsed("nodered_state_pub", STATE_INTERVAL_MS):
        publish_state_snapshot()


# End of nodered_client
