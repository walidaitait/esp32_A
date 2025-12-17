# ota_update.py
import network #type: ignore
import urequests #type: ignore
import machine #type: ignore
import time
import os
from machine import Pin #type: ignore
from wifi_config import WIFI_SSID, WIFI_PASSWORD

# --- Configurazioni ---
UPDATE_BUTTON_PIN = 16        # GPIO del pulsante
UPDATE_HOLD_TIME = 5          # secondi da tenere premuto
NODE_RED_IP = "10.182.4.179"  # IP PC con Node-RED
NODE_RED_PORT = 1880
BASE_URL = f"http://{NODE_RED_IP}:{NODE_RED_PORT}/ota/"

DEBUG_LOG_FILE = "debug_log.txt"

# --- Funzione log ---
def log(name, message):
    msg = "[{}] {}".format(name, message)
    print(msg)
    try:
        with open(DEBUG_LOG_FILE, "a") as f:
            f.write(msg + "\n")
    except:
        pass


# --- Funzioni interne ---
def _connect_wifi(timeout=15):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    start = time.time()
    while not wlan.isconnected():
        if time.time() - start > timeout:
            log("ota_update", "WiFi connection failed")
            return False
        time.sleep(0.1)
    log("ota_update", f"Connected to WiFi: {WIFI_SSID}")
    return True


def _check_button_pressed():
    btn = Pin(UPDATE_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    start = time.time()
    while time.time() - start < UPDATE_HOLD_TIME:
        if btn.value() == 1:  # rilasciato
            return False
        time.sleep(0.05)
    return True


def _make_dirs(path):
    parts = path.split("/")
    for i in range(1, len(parts) + 1):
        folder = "/".join(parts[:i])
        try:
            os.mkdir(folder)
        except OSError:
            pass  # già esiste


def _download_file(filename):
    try:
        url = BASE_URL + "file/" + filename
        log("ota_update", f"Downloading {filename} from {url}")
        r = urequests.get(url)
        if r.status_code == 200:
            if "/" in filename:
                folder_path = "/".join(filename.split("/")[:-1])
                _make_dirs(folder_path)
            with open(filename, "w") as f:
                f.write(r.text)
            log("ota_update", f"{filename} updated successfully")
        else:
            log("ota_update", f"Failed to download {filename} (status {r.status_code})")
        r.close()
    except Exception as e:
        log("ota_update", f"Exception downloading {filename}: {e}")


def _get_files_list():
    try:
        url = BASE_URL + "list"
        r = urequests.get(url)
        if r.status_code == 200:
            data = r.json()
            files = data.get("files", [])
            r.close()
            log("ota_update", f"Found {len(files)} file(s) on Node-RED")
            return files
        else:
            log("ota_update", f"Failed to get file list (status {r.status_code})")
            r.close()
            return []
    except Exception as e:
        log("ota_update", f"Exception getting file list: {e}")
        return []


# --- Funzione pubblica ---
def check_and_update():
    """Controlla pulsante e avvia OTA se necessario"""
    log("ota_update", "Checking update button...")
    if _check_button_pressed():
        log("ota_update", "Update button pressed. Starting OTA update.")
        if not _connect_wifi():
            log("ota_update", "OTA aborted due to WiFi failure")
            return
        files = _get_files_list()
        if not files:
            log("ota_update", "No files to update. Aborting OTA.")
            return
        for f in files:
            _download_file(f)
        log("ota_update", "OTA update completed. Rebooting...")
        time.sleep(1)
        machine.reset()
    else:
        log("ota_update", "Update button not pressed. Continuing normal execution.")

