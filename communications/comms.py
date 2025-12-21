from communications.mqtt_client import publish_data
import config
from timers import elapsed
import state
from debug import log


def log_sensor_data():
    if not elapsed("publish", config.PUBLISH_INTERVAL):
        return
    # Build a single payload with all sensor readings plus button state
    sensor_data = dict(state.sensor_data)
    sensor_data["buttons"] = state.button_state
    publish_data(sensor_data)    

# def state_update():
    


def send_communications():
    log_sensor_data()
    