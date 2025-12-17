from mqtt_client import publish_data
import config
from timers import elapsed
import state
from debug import log


def log_sensor_data():
    if not elapsed("publish", config.PUBLISH_INTERVAL):
        return
    sensor_data = {
                "temperature": state.sensor_data["temperature"],
                "co": state.sensor_data["co"],
                "acc": state.sensor_data["acc"],
                "buttons": state.button_state
                "ultrasonic_distance_cm": state.ultrasonic_distance_cm
            }
    publish_data(sensor_data)    

# def state_update():
    


def send_communications():
    log_sensor_data()
    