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

BASE_URL_ROOT = "https://raw.githubusercontent.com/walidaitait/esp32_A/main/"
FIRMWARE_FOLDER = "test_firmware_b"  # Change this if folder name changes
BASE_URL = BASE_URL_ROOT + FIRMWARE_FOLDER + "/"
ONSTART_CONFIG_FILE = "onstart_config.json"  # Downloaded config file name
ONSTART_CONFIG_URL = BASE_URL_ROOT + ONSTART_CONFIG_FILE  # Full URL to download
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


def _download_onstart_config():
    """Download onstart_config.json from server.
    
    Returns:
        bool: True if downloaded successfully, False otherwise
    """
    log("ota", "Downloading onstart_config.json")
    try:
        gc.collect()
        r = urequests.get(ONSTART_CONFIG_URL)
        if r.status_code != 200:
            log("ota", "HTTP error " + str(r.status_code) + " for onstart_config")
            r.close()
            return False
        
        with open(ONSTART_CONFIG_FILE, "w") as f:
            f.write(r.text)
        
        r.close()
        gc.collect()
        log("ota", "onstart_config.json downloaded")
        return True
    except Exception as e:
        log("ota", "Error downloading onstart_config: " + str(e))
        return False


def _read_onstart_config():
    """Read onstart_config.json and check if update is requested for this board.
    
    Returns:
        bool: True if update requested in onstart config, False otherwise
    """
    import json
    try:
        with open(ONSTART_CONFIG_FILE, "r") as f:
            config = json.load(f)
        
        # Check if update is requested for ESP32-B
        update_requested = config.get("esp32_b", {}).get("update_requested", False)
        
        if update_requested:
            log("ota", "onstart_config: Update requested for ESP32-B")
        else:
            log("ota", "onstart_config: No update requested")
        
        return update_requested
    except Exception as e:
        log("ota", "Error reading onstart_config: " + str(e))
        return False


def _cleanup_onstart_config():
    """Remove the downloaded onstart_config.json file."""
    try:
        os.remove(ONSTART_CONFIG_FILE)
        log("ota", "onstart_config.json removed")
    except:
        pass  # File might not exist, that's OK

# ================== PUBLIC ==================

def check_and_update():
    """Check for OTA update with new flow:
    
    1. Check if config.json exists
       - If NO: First installation, download all files
       - If YES: Proceed to step 2
    
    2. Connect to WiFi and download onstart_config.json
       - If download succeeds: Check if update_requested for this board
       - If update requested in onstart_config: Set should_update = True
    
    3. Check local config.json for ota_update_pending flag
    
    4. Check if button is pressed (if enabled)
    
    5. Perform update if requested from any source
    
    6. Cleanup: Remove onstart_config.json at the end
    """
    import json
    
    should_update = False
    is_first_install = False
    button_enabled = True  # Default to True for backwards compatibility
    config_data = {}  # Initialize to empty dict
    
    # STEP 1: Check if config.json exists
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
    
    # STEP 2: If NOT first install, connect WiFi and check onstart_config
    if not is_first_install:
        log("ota", "Connecting to WiFi to check onstart_config")
        if _connect_wifi():
            # Download onstart_config.json
            if _download_onstart_config():
                # Read and check if update is requested
                if _read_onstart_config():
                    log("ota", "Update requested via onstart_config")
                    should_update = True
        else:
            log("ota", "WiFi connection failed, skipping onstart_config check")
            # WiFi failed, cleanup and return (abort OTA)
            _cleanup_onstart_config()
            return
    
    # Read button enabled flag from config
    if not is_first_install:
        button_enabled = config_data.get("ota_button_enabled", True)
    
    # STEP 3: Check if OTA update is pending in local config.json
    if not is_first_install and config_data.get("ota_update_pending", False):
        log("ota", "OTA update pending flag found in local config.json")
        should_update = True
    
    # STEP 4: Check if button is pressed (only if enabled and update not already triggered)
    if not should_update and button_enabled:
        log("ota", "Checking update button")
        if _check_button_pressed():
            log("ota", "Update button pressed")
            should_update = True
        else:
            log("ota", "Button not pressed, skipping OTA")
    elif not should_update and not button_enabled:
        log("ota", "OTA button disabled in config, skipping button check")
    
    # If no update needed, cleanup and return
    if not should_update:
        _cleanup_onstart_config()
        return
    
    # STEP 5: Perform OTA update
    log("ota", "Update requested")

    # Connect WiFi if not already connected (first install case)
    if is_first_install and not _connect_wifi():
        log("ota", "OTA aborted (WiFi)")
        _cleanup_onstart_config()
        return

    files = _get_file_list()
    if not files:
        log("ota", "No files to update")
        # Clear the pending flag before returning
        if not is_first_install:
            _clear_ota_pending_flag()
        _cleanup_onstart_config()
        return

    ok = True
    for f in files:
        if not _download_file(f):
            ok = False

    # STEP 6: Cleanup and finalize
    _cleanup_onstart_config()
    
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
