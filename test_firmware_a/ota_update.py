# ota_update.py - TEST FIRMWARE VERSION
import network  # type: ignore
import urequests  # type: ignore
import machine  # type: ignore
from time import time, sleep  # type: ignore
import os
import gc
from machine import Pin  # type: ignore

from config.wifi_config import WIFI_SSID, WIFI_PASSWORD

# ================== CONFIG ==================

BASE_URL_ROOT = "https://raw.githubusercontent.com/walidaitait/esp32_A/main/"
FIRMWARE_FOLDER = "test_firmware_a"  # Change this if folder name changes
BASE_URL = BASE_URL_ROOT + FIRMWARE_FOLDER + "/"
CHUNK_SIZE = 1024  # bytes per read while streaming

# OTA button
UPDATE_BUTTON_PIN = 16
UPDATE_HOLD_TIME = 5  # seconds

# ================== LOG ==================

def log(name, message):
    msg = "[{}] {}".format(name, message)
    print(msg)

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
        sleep(0.2)

    log("ota", "WiFi connected")
    return True

# ================== BUTTON ==================

def _check_button_pressed():
    btn = Pin(UPDATE_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    start = time()

    while time() - start < UPDATE_HOLD_TIME:
        if btn.value() == 0:  # released
            return False
        sleep(0.05)

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

def _check_remote_version(local_version):
    """Check if remote firmware version is newer than local version.
    
    Args:
        local_version: Current firmware version number
    
    Returns:
        bool: True if remote version is newer, False otherwise
    """
    import json
    try:
        gc.collect()
        url = BASE_URL + "config/config.json"
        log("ota", "  - Downloading config from: " + url)
        
        r = urequests.get(url)
        if r.status_code != 200:
            log("ota", "  - ERROR: HTTP {} (failed to fetch remote config)".format(r.status_code))
            r.close()
            return False
        
        log("ota", "  - Successfully downloaded remote config")
        remote_config = r.json()
        r.close()
        
        remote_version = remote_config.get("firmware_version", None)
        log("ota", "  - Local version: {} | Remote version: {}".format(local_version, remote_version))
        
        if remote_version is None:
            log("ota", "  - ERROR: Remote config has no firmware_version field")
            return False
        
        if remote_version > local_version:
            log("ota", "  - UPDATE AVAILABLE: {}".format(remote_version) + " > " + str(local_version))
            return True
        else:
            log("ota", "  - Version check: local is up to date")
            return False
            
    except Exception as e:
        log("ota", "  - ERROR checking remote version: " + str(e))
        return False




# ================== PUBLIC ==================

def check_and_update():
    """Check for OTA update with simplified flow:
    
    1. Check if config.json exists
       - If NO: First installation, download all files
       - If YES: Proceed to step 2
    
    2. Check local config.json for ota_update_pending flag
       - If true: Perform update
       - If false: Proceed to step 3
    
    3. Check if button is pressed (5 seconds hold)
       - If pressed: Perform update
       - If not pressed: Proceed to step 4
    
    4. Check remote version on GitHub
       - If remote version > local version: Perform update
       - If not: Exit without update
    """
    import json
    
    should_update = False
    is_first_install = False
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
    
    # STEP 2: Check if OTA update is pending in local config.json
    if not is_first_install and config_data.get("ota_update_pending", False):
        log("ota", "OTA update pending flag found in config.json")
        should_update = True
    
    # STEP 3: Check if button is pressed (only if update not already triggered)
    if not should_update:
        log("ota", "Checking update button (hold for 5 seconds)")
        if _check_button_pressed():
            log("ota", "Update button pressed")
            should_update = True
        else:
            log("ota", "Button not pressed, checking remote version")
    
    # STEP 4: Check remote version on GitHub (only if update not already triggered)
    if not should_update and not is_first_install:
        # Need WiFi to check remote version
        log("ota", "STEP 4: Checking remote version on GitHub")
        if not _connect_wifi():
            log("ota", "STEP 4 FAILED: Cannot check remote version - WiFi failed")
            return
        
        local_version = config_data.get("firmware_version", 0)
        log("ota", "STEP 4: Local version = {}".format(local_version))
        if _check_remote_version(local_version):
            log("ota", "STEP 4 SUCCESS: Newer version available on GitHub - will download")
            should_update = True
        else:
            log("ota", "STEP 4: Local version is already up to date")
            return
    
    # If no update needed, return
    if not should_update:
        return
    
    # STEP 4: Perform OTA update
    log("ota", "Update requested")

    # Connect WiFi if not already connected (first install case)
    if is_first_install and not _connect_wifi():
        log("ota", "OTA aborted (WiFi)")
        return
    
    # For non-first-install, ensure WiFi connection
    if not is_first_install and not _connect_wifi():
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
        if not is_first_install:
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
