import ota_update
ota_update.check_and_update()


from debug import log, debug_flags
from config import SIMULATE_SENSORS
from wifi_config import MQTT_ENABLE
from logic.logic import evaluate_logic
from commands.commands import update_output_commands
from communications.comms import send_communications
import state

if SIMULATE_SENSORS:
    from simulate.simulate_sensors import simulate_all as read_sensors
    log("main", "Simulation mode: ON")
else:
    log("main", "Simulation mode: OFF")
#     from sensors_temperature import read_temperature
    from sensors.sensors_co import read_co
    from sensors.buttons import read_buttons
    from sensors.sensors_accelerometer import read_accelerometer
    from sensors.sensors_ultrasonic import init_ultrasonic, read_ultrasonic


if MQTT_ENABLE:
    log("main", "MQTT is enabled. Proceeding with wifi connection")
    from communications.mqtt_client import connect_wifi, init_mqtt, publish_data
    from wifi_config import WIFI_SSID, WIFI_PASSWORD




def onstart():

    if MQTT_ENABLE:
        log("main", "MQTT is enabled. Proceeding with wifi connection")
#         from time_sync import sync_time
#         sync_time()
        connect_wifi(WIFI_SSID, WIFI_PASSWORD)
        init_mqtt()
        # init_sensors()  #this function will be added later


def main():
    first_run = True
    onstart()
    

    while True:
        if first_run:
            log("main", "Main loop started")
            first_run = False
        # Uncomment the following lines when the respective modules are implemented
        read_buttons()
        read_co()
        read_accelerometer()
        read_ultrasonic()
#         read_temperature()
#         read_sensors()

        evaluate_logic()
        update_output_commands()
        
        # Publish sensor data via MQTT
        if MQTT_ENABLE:
            send_communications()


main()


