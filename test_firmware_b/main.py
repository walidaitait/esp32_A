"""Firmware - Actuators (ESP32-B)

Control module for:
  - DFRobot LED modules (DFR0021-G/B/R)
  - SG90 9g Servo
  - LCD 1602A with I2C backpack
  - Sunfounder Passive buzzer
  - DFPlayer Mini + 4Ω 3W speaker

Architecture:
- core.wifi: WiFi connection management
- core.actuator_loop: Non-blocking actuator update loop
- actuators.*: Individual actuator drivers
- debug.*: UDP logging
"""


# Import OTA first and check for updates BEFORE importing anything else
import ota_update
ota_update.check_and_update()

# === SIMULATION MODE ===
# Set to True to use simulated actuator values instead of real hardware
SIMULATE_ACTUATORS = True

from debug.debug import log, init_remote_logging
from core import wifi
from core import actuator_loop
from communication import espnow_communication


def main():
    """Main entry point for actuator firmware."""
    log("main", "Starting actuator firmware (B)")
    
    # === INITIALIZATION PHASE (blocking allowed here) ===
    
    # Connect to WiFi for UDP logging
    log("main", "Phase 1: WiFi connection")
    if not wifi.init_wifi():
        log("main", "WARNING - WiFi connection failed, continuing anyway")
    
    # Initialize remote UDP logging
    log("main", "Phase 2: Remote logging initialization")
    init_remote_logging('B')
    
    # Initialize all actuators (or simulation mode)
    log("main", "Phase 3: Actuator initialization")
    if SIMULATE_ACTUATORS:
        from actuators import simulation
        log("main", "SIMULATION MODE - Using simulated actuators")
        if not simulation.init_simulation():
            log("main", "WARNING - Simulation initialization failed")
        actuator_loop.set_simulation_mode(True)
    else:
        log("main", "HARDWARE MODE - Using real actuators")
        if not actuator_loop.initialize():
            log("main", "WARNING - Some actuators failed to initialize")
        actuator_loop.set_simulation_mode(False)
    
    # Initialize ESP-NOW communication (after WiFi and actuators)
    log("main", "Phase 4: ESP-NOW communication initialization")
    if not espnow_communication.init_espnow_comm():
        log("main", "WARNING - ESP-NOW initialization failed")

    log("main", "Initialization complete. Entering main loop.")

    # === MAIN LOOP (non-blocking only) ===
    
    while True:
        try:
            # Update all actuators without blocking
            actuator_loop.update()
            
            # Update ESP-NOW communication
            espnow_communication.update()
            
            # Minimal CPU usage - yield to other tasks
            # The update() function uses elapsed() timers internally
            # so it's OK to call this very frequently (near-zero overhead)
            
        except KeyboardInterrupt:
            log("main", "Firmware stopped by user")
            break
        except Exception as e:
            log("main", "ERROR in main loop: {}".format(e))
            # Loop continues, no blocking sleep


if __name__ == "__main__":
    main()
