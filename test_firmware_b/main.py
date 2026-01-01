"""
Firmware - Actuators (ESP32-B)
Control module for:
  - DFRobot LED modules (DFR0021-G/B/R)
  - SG90 9g Servo
  - LCD 1602A with I2C backpack
  - Sunfounder Passive buzzer
  - DFPlayer Mini + 4Ω 3W speaker
"""

# Import OTA first and check for updates BEFORE importing anything else
import ota_update
ota_update.check_and_update()

import time
from debug.debug import log, init_remote_logging
from core import state
from core.timers import elapsed
from comms import command_handler

# Actuator modules
from actuators import leds, servo, lcd, buzzer, audio


def init_actuators():
    """Initialize all actuators and communication system."""
    log("main", "Initializing actuators...")

    status = {}

    status["LED modules"] = leds.init_leds()
    status["Servo"] = servo.init_servo()
    status["LCD 16x2"] = lcd.init_lcd()
    status["Buzzer"] = buzzer.init_buzzer()
    status["DFPlayer"] = audio.init_audio()

    for name, ok in status.items():
        result = "OK" if ok else "FAILED"
        log("main", "{}: {}".format(name, result))
    
    # Initialize communication system
    log("main", "Initializing communication system...")
    comm_ok = command_handler.init()
    log("main", "Communication: {}".format("OK" if comm_ok else "FAILED"))


def main():
    log("main", "Starting firmware...")
    
    # Initialize remote logging (for centralized monitoring)
    log("main", "Initializing remote UDP logging...")
    init_remote_logging('B')  # 'B' for ESP32-B
    
    init_actuators()

    log("main", "Entering main loop")

    while True:
        try:
            # Non-blocking loop: prevent blocking with elapsed()
            if elapsed("main_loop", 100):
                pass
            
            # Update communication system (receive commands from A)
            command_handler.update()
            
            # Check if A is connected and log status periodically
            if elapsed("comm_status", 5000):
                if command_handler.is_connected():
                    log("main", "ESP32-A: CONNECTED - receiving commands")
                else:
                    log("main", "ESP32-A: DISCONNECTED - waiting for connection...")
            
        except KeyboardInterrupt:
            log("main", "Firmware stopped by user")
            break
        except Exception as e:
            log("main", "ERROR in main loop: {}".format(e))
            # Skip error recovery with elapsed() instead of blocking
            if elapsed("error_recovery", 1000):
                pass


if __name__ == "__main__":
    main()
