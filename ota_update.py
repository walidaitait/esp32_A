# ota_update.py
import network  # type: ignore
import urequests  # type: ignore
import machine  # type: ignore
import time
import os
from machine import Pin  # type: ignore

from wifi_config import WIFI_SSID, WIFI_PASSWORD

# ================== CONFIG ==================

BASE_URL = "https://raw.githubusercontent.com/walidaitait/esp32_A/main/"

# OTA button
UPDATE_BUTTON_PIN = 16
UPDATE_HOLD_TIME = 5  # seconds

# ================== LOG ==================

def log(name, message):
    msg = "[{}] {}".format(name, message)
    print(msg)
    try:
        with open("ota_log.txt", "a") as f:
            f.write(msg + "\n")
    except:
        pass

# ================== WIFI ==================

def _connect_wifi(timeout=15):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    start = time.time()
    while not wlan.isconnected():
        if time.time() - start > timeout:
            log("ota", "WiFi connection failed")
            return False
        time.sleep(0.2)

    log("ota", "WiFi connected")
    return True

# ================== BUTTON ==================

def _check_button_pressed():
    btn = Pin(UPDATE_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    start = time.time()

    while time.time() - start < UPDATE_HOLD_TIME:
        if btn.value() == 1:  # released
            return False
        time.sleep(0.05)

    return True

# ================== FILESYSTEM ==================

def _ensure_dirs(filepath):
    if "/" not in filepath:
        return

    parts = filepath.split("/")[:-1]
    path = ""
    for p in parts:
        path = p if path == "" else path + "/" + p
        try:
            os.mkdir(path)
        except OSError:
            pass

# ================== OTA CORE ==================

def _download_file(filename):
    url = BASE_URL + filename
    log("ota", "Downloading " + filename)

    try:
        r = urequests.get(url)
        if r.status_code != 200:
            log("ota", "HTTP error " + str(r.status_code))
            r.close()
            return False

        _ensure_dirs(filename)

        with open(filename, "w") as f:
            f.write(r.text)

        r.close()
        log("ota", "Updated " + filename)
        return True

    except Exception as e:
        log("ota", "Download error: " + str(e))
        return False

def _get_file_list():
    try:
        r = urequests.get(BASE_URL + "filelist.json")
        files = r.json()  # MUST be a list
        r.close()

        if not isinstance(files, list):
            log("ota", "filelist.json is not a list")
            return []

        return files

    except Exception as e:
        log("ota", "Failed to read file list: " + str(e))
        return []

# ================== PUBLIC ==================

def check_and_update():
    log("ota", "Checking update button")

    if not _check_button_pressed():
        log("ota", "Button not pressed, skipping OTA")
        return

    log("ota", "Update requested")

    if not _connect_wifi():
        log("ota", "OTA aborted (WiFi)")
        return

    files = _get_file_list()
    if not files:
        log("ota", "No files to update")
        return

    ok = True
    for f in files:
        if not _download_file(f):
            ok = False

    if ok:
        log("ota", "OTA completed, rebooting")
        time.sleep(1)
        machine.reset()
    else:
        log("ota", "OTA finished with errors")
