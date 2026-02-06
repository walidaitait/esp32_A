"""ESP32-B Actuator Firmware - Main entry point.

Imported by: MicroPython runtime
Imports: ota_update, debug.debug, core.*, communication.*, config.config

Controls actuators based on sensor data received from ESP32-A via ESP-NOW:
- DFRobot LED modules (DFR0021-G/B/R): Status indicators
- SG90 9g Servo: Automatic gate control (requires alarm_level="danger")
- LCD 1602A with I2C: Display status messages
- Sunfounder Passive buzzer: Alarm tones
- DFPlayer Mini + 4Ω 3W speaker: Voice announcements

Architecture:
- communication.wifi: WiFi connection management
- core.actuator_loop: Non-blocking actuator update orchestration
- core.state: Shared state between modules
- actuators.*: Individual actuator drivers (leds, servo, lcd, buzzer, audio)
- communication.espnow_communication: Receives sensor data from Board A
- communication.udp_commands: Development commands
- debug.*: UDP logging to development PC
- logic.emergency: SOS detection via button press

Main loop is non-blocking: all blocking operations must be avoided.
"""


# Import OTA first and check for updates BEFORE importing anything else
import ota_update
ota_update.check_and_update()

from debug.debug import log, init_remote_logging, set_log_enabled, set_all_logs
from communication import wifi
from core import actuator_loop
from core import state
from communication import espnow_communication
from communication import udp_commands
from config import config

# === DISABLE UNNECESSARY LOGS FOR TESTING ===
set_all_logs(False)
set_log_enabled("main", True)
set_log_enabled("actuator.servo", True)
set_log_enabled("actuator.servo.gate", True)
set_log_enabled("actuator.servo.debug", True)
set_log_enabled("actuator.servo.test", True)
#set_log_enabled("communication.udp_cmd", True)
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
    
    # Initialize button (if enabled) - needed for emergency SOS detection
    log("main", "Phase 3a: Button initialization")
    if config.BUTTON_ENABLED:
        from actuators import buttons as buttons_module
        if not buttons_module.init_buttons():
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
            
            # Check if sensor state from A is stale (no update for >15s)
            if state.received_sensor_state["last_update"] is not None:
                from time import ticks_ms, ticks_diff  # type: ignore
                elapsed_since_update = ticks_diff(ticks_ms(), state.received_sensor_state["last_update"])
                if elapsed_since_update > 15000:
                    if not state.received_sensor_state["is_stale"]:
                        log("main", "WARNING: Sensor data from A is stale (no update for 15s)")
                        state.received_sensor_state["is_stale"] = True
            
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
