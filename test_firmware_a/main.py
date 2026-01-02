"""Connection test main (ESP32-A → ESP32-B via ESP-NOW).

Temporarily disables sensor reads/logic; only ping/ack messages with counters.
"""

# Import OTA first
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
        wlan.config(mac=MAC_A_BYTES)
    except Exception:
        pass
    try:
        wlan.config(channel=1)
    except Exception:
        pass

    esp = espnow.ESPNow()
    esp.active(True)
    esp.add_peer(MAC_B_BYTES)
    return esp


def main():
    log("main", "main: Boot main loop")
    
    # Ensure WiFi is connected first
    log("main", "main: Connecting to WiFi...")
    if not ensure_wifi_connected():
        log("main", "main: WARNING - WiFi connection failed, continuing without remote logging")
    
    # Initialize remote logging (requires WiFi)
    log("main", "main: Initializing remote UDP logging...")
    init_remote_logging('A')  # 'A' for ESP32-A

    # ESP-NOW setup for ping/ack
    esp = setup_espnow()
    counter = 0

    while True:
        try:
            # Send numbered ping
            msg = "PING:{}".format(counter).encode()
            try:
                esp.send(MAC_B_BYTES, msg)
                log("main", "TX -> B {}".format(msg))
            except Exception as exc:
                log("main", "TX error: {}".format(exc))

            # Wait for ACK
            start = time.ticks_ms()
            got_ack = False
            while time.ticks_diff(time.ticks_ms(), start) < 2000:
                try:
                    mac, data = esp.recv(0)
                    if mac and data and data.startswith(b"ACK:"):
                        log("main", "RX ack {} from {}".format(data, mac))
                        got_ack = True
                        break
                except OSError:
                    pass
                except Exception as exc:
                    log("main", "RX error: {}".format(exc))
                    break
                time.sleep_ms(50)

            if not got_ack:
                log("main", "No ACK for {}".format(msg))

            counter += 1
            time.sleep_ms(1000)

        except KeyboardInterrupt:
            log("main", "Loop interrupted by user")
            break
        except Exception as e:
            log("main", "Exception: {}".format(e))
            time.sleep_ms(500)


if __name__ == "__main__":
    main()
