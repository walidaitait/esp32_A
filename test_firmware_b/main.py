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

from debug.debug import log, init_remote_logging, set_log_enabled, set_all_logs
from core import wifi
from core import actuator_loop
from core import state
from communication import espnow_communication
from communication import udp_commands
from config import config

# === DISABLE UNNECESSARY LOGS FOR TESTING ===
set_all_logs(False)
set_log_enabled("sensor.ultrasonic", True)
set_log_enabled("alarm.logic", True)
set_log_enabled("actuator.servo.gate", True)
set_log_enabled("main", True)

# === SIMULATION MODE (loaded from config) ===
SIMULATE_ACTUATORS = config.SIMULATE_ACTUATORS


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
    
    # Initialize button (if enabled)
    log("main", "Phase 3a: Button initialization")
    if config.BUTTON_ENABLED:
        from actuators import buttons
        if not buttons.init_buttons():
            log("main", "WARNING - Button initialization failed")
    
    # Initialize all actuators (or simulation mode)
    log("main", "Phase 3b: Actuator initialization")
    if SIMULATE_ACTUATORS:
        from actuators import simulation
        log("main", "SIMULATION MODE - Using simulated actuators")
        if not simulation.init_simulation():
            log("main", "WARNING - Simulation initialization failed")
        actuator_loop.set_simulation_mode(True)
        state.actuator_state["simulation_mode"] = True
    else:
        log("main", "HARDWARE MODE - Using real actuators")
        if not actuator_loop.initialize():
            log("main", "WARNING - Some actuators failed to initialize")
        actuator_loop.set_simulation_mode(False)
        state.actuator_state["simulation_mode"] = False
    
    # Initialize ESP-NOW communication (after WiFi and actuators)
    log("main", "Phase 4: ESP-NOW communication initialization")
    if not espnow_communication.init_espnow_comm():
        log("main", "WARNING - ESP-NOW initialization failed")
    
    # Initialize UDP command listener (after WiFi)
    log("main", "Phase 5: UDP command listener initialization")
    if not udp_commands.init():
        log("main", "WARNING - UDP command listener failed")

    log("main", "Initialization complete. Entering main loop.")

    # === MAIN LOOP (non-blocking only) ===
    
    while True:
        try:
            # === PRIORITY CHECK: System control commands ===
            # These take precedence over normal operation
            
            # Check for reboot request
            if state.system_control["reboot_requested"]:
                log("main", "Reboot requested - stopping all processes")
                state.system_control["reboot_requested"] = False
                import machine #type: ignore
                log("main", "Rebooting now...")
                machine.reset()
            
            # === NORMAL OPERATION ===
            
            # Read button state (if enabled)
            if config.BUTTON_ENABLED:
                from actuators import buttons
                buttons.read_buttons()
            
            # Update all actuators without blocking
            actuator_loop.update()
            
            # Update ESP-NOW communication
            espnow_communication.update()
            
            # Check for incoming UDP commands
            udp_commands.update()
            
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
