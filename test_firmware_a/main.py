"""Main entry point for ESP32-A (Sensor Board) firmware.

This module orchestrates sensor reading, alarm evaluation, and communication.
Imported by: None (entry point, executed directly on boot)
Imports: core.wifi, core.sensor_loop, core.state, communication.espnow_communication,
         communication.nodered_client, communication.udp_commands, config.config,
         debug.debug, ota_update

Architecture:
- OTA update check runs first before any imports
- WiFi initialization for UDP logging and MQTT
- Sensor initialization (real hardware or simulation mode)
- ESP-NOW communication to Board B
- UDP command listener for remote control
- Non-blocking main loop calls update() on all subsystems

Main loop responsibilities:
- Check system control flags (reboot, OTA)
- Monitor Board B connection health
- Update sensors and evaluate alarm logic
- Handle ESP-NOW bidirectional communication
- Process Node-RED/MQTT messages
- Handle UDP commands from external tools
"""


# Import OTA first
import ota_update
ota_update.check_and_update()

from debug.debug import log, init_remote_logging, set_log_enabled, set_all_logs
from core import wifi
from core import sensor_loop
from core import state
from communication import espnow_communication
from communication import nodered_client
from communication import udp_commands
from config import config

# === ENABLE TARGETED DEBUG LOGS (reduced noise) ===
set_all_logs(False)  # disable global spam
# Keep only what we need for TX/RX + MQTT/UDP + WiFi bring-up
set_log_enabled("main", True)
set_log_enabled("espnow_a", True)
set_log_enabled("communication.espnow", True)
set_log_enabled("communication.udp_cmd", True)
set_log_enabled("nodered", True)
set_log_enabled("wifi", True)
set_log_enabled("core.sensor", True)

# === SIMULATION MODE (loaded from config) ===
SIMULATE_SENSORS = config.SIMULATE_SENSORS


def main():
    """Main entry point for sensor firmware."""
    log("main", "Starting sensor firmware (A)")
    
    # === INITIALIZATION PHASE (blocking allowed here) ===
    
    # Connect to WiFi for UDP logging
    log("main", "Phase 1: WiFi connection")
    if not wifi.init_wifi():
        log("main", "WARNING - WiFi connection failed, continuing anyway")
    
    # Initialize remote UDP logging
    log("main", "Phase 2: Remote logging initialization")
    init_remote_logging('A')

    # Initialize Node-RED/Adafruit bridge (optional, non-blocking if disabled)
    log("main", "Phase 2b: Node-RED/Adafruit bridge initialization")
    nodered_client.init()
    
    # Initialize all sensors (or simulation mode)
    log("main", "Phase 3: Sensor initialization")
    if SIMULATE_SENSORS:
        from sensors import simulation
        log("main", "SIMULATION MODE - Using simulated sensors")
        if not simulation.init_simulation():
            log("main", "WARNING - Simulation initialization failed")
        sensor_loop.set_simulation_mode(True)
        state.simulation_mode = True
    else:
        log("main", "HARDWARE MODE - Using real sensors")
        if not sensor_loop.initialize():
            log("main", "WARNING - Some sensors failed to initialize")
        sensor_loop.set_simulation_mode(False)
        state.simulation_mode = False
    
    # Initialize ESP-NOW communication (after WiFi and sensors)
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
            
            # Check if actuator state from B is stale (no update for >15s)
            if state.received_actuator_state["last_update"] is not None:
                from time import ticks_ms, ticks_diff  # type: ignore
                elapsed_since_update = ticks_diff(ticks_ms(), state.received_actuator_state["last_update"])
                if elapsed_since_update > 15000:
                    if not state.received_actuator_state["is_stale"]:
                        log("main", "WARNING: Actuator data from B is stale (no update for 15s)")
                        state.received_actuator_state["is_stale"] = True
            
            # Update all sensors and evaluate alarm logic without blocking
            sensor_loop.update()
            
            # Update ESP-NOW communication
            espnow_communication.update()

            # Update Node-RED/Adafruit MQTT bridge
            nodered_client.update()
            
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
