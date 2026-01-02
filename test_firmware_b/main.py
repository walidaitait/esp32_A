"""Connection test main (ESP32-B, ESP-NOW echo/ack).

Temporarily disables actuator logic; only receives numbered messages from A,
logs them, and replies with ACK:<payload>.
"""

# Import OTA first and check for updates BEFORE importing anything else
import ota_update
ota_update.check_and_update()

import time
import network  # type: ignore
import espnow   # type: ignore
from debug.debug import log, init_remote_logging
from config.wifi_config import WIFI_SSID, WIFI_PASSWORD
from config.config import MAC_A_BYTES, MAC_B_BYTES


def ensure_wifi_connected():
    """Ensure WiFi is connected for communication and remote logging."""
    wlan = network.WLAN(network.STA_IF)

    if wlan.isconnected():
        log("main", "WiFi already connected: {}".format(wlan.ifconfig()[0]))
        return True

    log("main", "Connecting to WiFi...")
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    timeout = 15
    start = time.time()
    while not wlan.isconnected():
        if time.time() - start > timeout:
            log("main", "WiFi connection timeout")
            return False
        time.sleep(0.2)

    log("main", "WiFi connected: {}".format(wlan.ifconfig()[0]))
    return True


def setup_espnow():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    try:
        wlan.config(mac=MAC_B_BYTES)
    except Exception:
        pass
    try:
        wlan.config(channel=1)
    except Exception:
        pass

    esp = espnow.ESPNow()
    esp.active(True)
    esp.add_peer(MAC_A_BYTES)
    return esp


def main():
    log("main", "Starting ESP-NOW connection test (B)")

    # Ensure WiFi is connected first
    if not ensure_wifi_connected():
        log("main", "WARNING - WiFi connection failed, continuing without remote logging")

    # Initialize remote logging (requires WiFi)
    init_remote_logging('B')

    esp = setup_espnow()

    while True:
        try:
            mac, data = esp.recv(0)  # non-blocking
            if mac and data:
                log("main", "RX <- {} : {}".format(mac, data))

                # Send ACK back
                try:
                    ack = b"ACK:" + data
                    esp.send(mac, ack)
                    log("main", "TX ack -> {} : {}".format(mac, ack))
                except Exception as exc:
                    log("main", "ACK send error: {}".format(exc))

        except KeyboardInterrupt:
            log("main", "Firmware stopped by user")
            break
        except Exception as e:
            log("main", "ERROR in main loop: {}".format(e))
            time.sleep_ms(200)
        time.sleep_ms(50)


if __name__ == "__main__":
    main()
