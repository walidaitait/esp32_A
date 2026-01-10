# ota_update.py - Firmware OTA UPDATE module for ESP32-B
import network  # type: ignore
import urequests  # type: ignore
import machine  # type: ignore
from time import ticks_ms, ticks_diff, time, sleep  # type: ignore
import os
import gc
from machine import Pin  # type: ignore

from config.wifi_config import WIFI_SSID, WIFI_PASSWORD

# Local lightweight timer helper to avoid depending on project modules
_timers = {}


def _elapsed(name, interval_ms):
    now = ticks_ms()
    last = _timers.get(name, 0)
    if ticks_diff(now, last) >= interval_ms:
        _timers[name] = now
        return True
    return False

# ================== CONFIG ==================

# Use different branch/folder if you want to separate updates for A and B
BASE_URL = "https://raw.githubusercontent.com/walidaitait/esp32_A/main/test_firmware_b/"
CHUNK_SIZE = 1024  # bytes per read while streaming

# OTA button (use a free GPIO that doesn't conflict with actuators)
UPDATE_BUTTON_PIN = 18  # GPIO18
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

    start = time()
    while not wlan.isconnected():
        if time() - start > timeout:
            log("ota", "WiFi connection failed")
            return False
        # Use non-blocking wait with local elapsed helper
        if _elapsed("wifi_check", 200):
            pass

    log("ota", "WiFi connected")
    return True

# ================== BUTTON ==================

def _check_button_pressed():
    btn = Pin(UPDATE_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    start = time()

    while time() - start < UPDATE_HOLD_TIME:
        if btn.value() == 0:  # released
            return False
        # Use non-blocking wait with local elapsed helper
        if _elapsed("button_check", 50):
            pass

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
        gc.collect()  # free heap before TLS handshake
        r = urequests.get(url)
        if r.status_code != 200:
            log("ota", "HTTP error " + str(r.status_code))
            r.close()
            return False

        _ensure_dirs(filename)

        # Stream to file to reduce RAM usage; fall back to r.text if needed
        if hasattr(r, "raw"):
            with open(filename, "wb") as f:
                while True:
                    chunk = r.raw.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
        else:
            with open(filename, "w") as f:
                f.write(r.text)

        r.close()
        gc.collect()
        log("ota", "Updated " + filename)
        return True

    except Exception as e:
        log("ota", "Download error: " + str(e))
        return False


def _get_file_list():
    try:
        gc.collect()  # free heap before TLS handshake
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

def _clear_ota_pending_flag():
    """Clear the OTA pending flag from config.json after successful update"""
    import json
    try:
        try:
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
        except:
            with open("config.json", "r") as f:
                config_data = json.load(f)
        
        config_data["ota_update_pending"] = False
        
        try:
            with open("config/config.json", "w") as f:
                json.dump(config_data, f)
        except:
            with open("config.json", "w") as f:
                json.dump(config_data, f)
        
        log("ota", "OTA pending flag cleared")
    except Exception as e:
        log("ota", "Error clearing OTA flag: " + str(e))

# ================== PUBLIC ==================

def check_and_update():
    """Check for OTA update: button press OR config flag (post-reboot).
    
    On first boot (no config.json): Downloads all files.
    On subsequent boots: Checks config.json for ota_update_pending flag.
    """
    import json
    
    should_update = False
    is_first_install = False
    button_enabled = True  # Default to True for backwards compatibility
    config_data = {}  # Initialize to empty dict
    
    # Check if config.json exists
    try:
        with open("config/config.json", "r") as f:
            config_data = json.load(f)
    except:
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
        except:
            # First installation: no config.json found
            log("ota", "First installation detected - will download all files")
            is_first_install = True
            should_update = True
    
    # Read button enabled flag from config
    if not is_first_install:
        button_enabled = config_data.get("ota_button_enabled", True)
    
    # Check if OTA update is pending in config (set by remote command)
    if not is_first_install and config_data.get("ota_update_pending", False):
        log("ota", "OTA update pending flag found in config")
        should_update = True
    
    # Check if button is pressed (only if enabled and update not already triggered by config)
    if not should_update and button_enabled:
        log("ota", "Checking update button")
        if not _check_button_pressed():
            log("ota", "Button not pressed, skipping OTA")
            return
        log("ota", "Update button pressed")
        should_update = True
    elif not should_update and not button_enabled:
        log("ota", "OTA button disabled in config, skipping button check")
        return
    
    if not should_update:
        return
    
    log("ota", "Update requested")

    if not _connect_wifi():
        log("ota", "OTA aborted (WiFi)")
        return

    files = _get_file_list()
    if not files:
        log("ota", "No files to update")
        # Clear the pending flag before returning
        if not is_first_install:
            _clear_ota_pending_flag()
        return

    ok = True
    for f in files:
        if not _download_file(f):
            ok = False

    if ok:
        log("ota", "OTA completed, clearing flag and rebooting")
        # Clear the pending flag before reboot
        _clear_ota_pending_flag()
        sleep(1)
        machine.reset()
    else:
        log("ota", "OTA finished with errors")
        # Don't clear flag on error - will retry on next boot


def perform_ota_update():
    """Perform OTA update without button press (triggered by command).
    
    Returns:
        bool: True if update completed successfully, False otherwise
    """
    log("ota", "OTA update triggered by command")

    if not _connect_wifi():
        log("ota", "OTA aborted (WiFi)")
        return False

    files = _get_file_list()
    if not files:
        log("ota", "No files to update")
        return False

    ok = True
    for f in files:
        if not _download_file(f):
            ok = False

    if ok:
        log("ota", "OTA completed, rebooting")
        sleep(1)
        machine.reset()
        return True  # Won't reach here due to reset
    else:
        log("ota", "OTA finished with errors")
        return False
