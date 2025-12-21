import network #type: ignore
import time
from simple import MQTTClient #type: ignore 
import wifi_config #type: ignore
import json
from debug import log, set_debug_flags #type: ignore

CLIENT_ID = "ESP32_A"

mqtt_client = None


def _handle_command(topic, msg):
    """Handle incoming MQTT commands to toggle debug flags."""
    try:
        payload = json.loads(msg)
    except Exception as e:
        print("[debug] invalid JSON command: {}".format(e))
        return

    if isinstance(payload, dict):
        # Accept {"flags": {"co": true, "temperature": false}} or {"flag": "co", "enabled": true}
        if "flags" in payload and isinstance(payload["flags"], dict):
            set_debug_flags(payload["flags"])
        elif "flag" in payload and "enabled" in payload:
            set_debug_flags({payload["flag"]: payload["enabled"]})
        else:
            print("[debug] unsupported command shape: {}".format(payload))
    else:
        print("[debug] command payload must be an object: {}".format(payload))

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.disconnect()
    time.sleep(1)
    if not wlan.isconnected():
        log("mqtt_client", "Connecting to WiFi...")
        wlan.connect(ssid, password)
        while not wlan.isconnected():
            time.sleep(0.5)    
#         if connect_attempt == 50:
#             debug.log("mqtt_client", "Wifi NOT connected.")
    log("mqtt_client", f"WiFi connected: {wlan.ifconfig()}")
    return wlan

def init_mqtt():
    global mqtt_client
    if not wifi_config.MQTT_ENABLE:
        log("mqtt_client", "MQTT disabled in wifi_config.")
        return None

#     mqtt_client = MQTTClient(CLIENT_ID, config.MQTT_BROKER, port=config.MQTT_PORT)
#     mqtt_client = MQTTClient(CLIENT_ID, config.MQTT_BROKER, port=config.MQTT_PORT, user=config.MQTT_USER, password=config.MQTT_PASSWORD)
    mqtt_client = MQTTClient(CLIENT_ID, wifi_config.MQTT_BROKER, port=wifi_config.MQTT_PORT, user=wifi_config.MQTT_USER, password=wifi_config.MQTT_PASSWORD, ssl=True)
    try:
        mqtt_client.set_callback(_handle_command)
        mqtt_client.connect()
        mqtt_client.subscribe(wifi_config.MQTT_DEBUG_TOPIC)
        log("mqtt_client", "MQTT connected and subscribed for debug control.")
    except Exception as e:
        log("mqtt_client", f"MQTT connection failed: {e}")
        mqtt_client = None
    return mqtt_client

def publish_data(data):
    if mqtt_client is None:
        return
    try:
        payload = json.dumps(data)
        mqtt_client.publish(wifi_config.MQTT_TOPIC, payload)
        log("mqtt_client", f"MQTT published payload: {payload}")
    except Exception as e:
        log("mqtt_client", f"Failed to publish: {e}")


def poll_mqtt():
    if mqtt_client is None:
        return
    try:
        mqtt_client.check_msg()
    except Exception as e:
        log("mqtt_client", f"MQTT check_msg failed: {e}")

