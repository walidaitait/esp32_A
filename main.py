import ota_update
ota_update.check_and_update()


from debug import log, debug_flags
import config
from wifi_config import MQTT_ENABLE
from timers import elapsed
import state
from logic.logic import evaluate_logic
from commands.commands import update_output_commands
from communications.espnow_link import EspNowLink
from communications.comms import send_communications

if config.SIMULATE_SENSORS:
    from simulate.sensors import simulate_all as read_sensors
    log("main", "Simulation mode: ON")
else:
    log("main", "Simulation mode: OFF")
    from sensors.co import init_co, read_co
    from sensors.buttons import init_buttons, read_buttons
    from sensors.accelerometer import init_accelerometer, read_accelerometer
    from sensors.ultrasonic import init_ultrasonic, read_ultrasonic
    from sensors.temperature import init_temperature, read_temperature
    from sensors.heart_rate import init_heart_rate, read_heart_rate


if MQTT_ENABLE:
    log("main", "MQTT is enabled. Proceeding with wifi connection")
    from communications.mqtt_client import connect_wifi, init_mqtt, publish_data, poll_mqtt
    from wifi_config import WIFI_SSID, WIFI_PASSWORD



espnow = None

def onstart():

    if MQTT_ENABLE:
        log("main", "MQTT is enabled. Proceeding with wifi connection")
#         from time_sync import sync_time
#         sync_time()
        global espnow
        espnow=EspNowLink(peer=config.ESP32_B_PEER_MAC)
        espnow.start()
        connect_wifi(WIFI_SSID, WIFI_PASSWORD)
        init_mqtt()
        # init_sensors()  #this function will be added later


def main():
    first_run = True
    onstart()
    
    if not config.SIMULATE_SENSORS:
        co_ok = init_co()
        if not co_ok:
            log("main", "CO sensor not available - continuing without it")
        
        btn_ok = init_buttons()
        if not btn_ok:
            log("main", "Buttons not available - continuing without them")
        
        acc_ok = init_accelerometer()
        if not acc_ok:
            log("main", "Accelerometer not available - continuing without it")
        
        ultra_ok = init_ultrasonic()
        if not ultra_ok:
            log("main", "Ultrasonic sensor not available - continuing without it")
        
        temp_ok = init_temperature()
        if not temp_ok:
            log("main", "Temperature sensor not available - continuing without it")
        
        hr_ok = init_heart_rate()
        if not hr_ok:
            log("main", "Heart rate sensor not available - continuing without it")

    while True:
        if first_run:
            log("main", "ESP32_A started")
            first_run = False
        
        # Poll MQTT for incoming debug commands
        if MQTT_ENABLE:
            poll_mqtt()
        
        espnow.poll()

        if elapsed("tx", 100):
            espnow.send_cmd(state.build_command())
        if config.SIMULATE_SENSORS:
            read_sensors()
        else:
            read_buttons()
            read_co()
            read_accelerometer()
            read_ultrasonic()
            read_heart_rate()
            read_temperature()

        evaluate_logic()
        update_output_commands()
        
        # Publish sensor data via MQTT
        if MQTT_ENABLE:
            send_communications()


main()


