"""Main loop: sensor reading + alarm logic (independent).

Reads sensors continuously and evaluates alarm logic.
No communication with B - sensors and logic are standalone.

Architecture:
- core.wifi: WiFi connection management
- core.sensor_loop: Non-blocking sensor read and alarm evaluation loop
- sensors.*: Individual sensor drivers
- logic.alarm_logic: Alarm evaluation
- debug.*: UDP logging
"""


# Import OTA first
import ota_update
ota_update.check_and_update()

from debug.debug import log, init_remote_logging, set_log_enabled, set_all_logs
from core import wifi
from core import sensor_loop
from core import state
from communication import espnow_communication
from communication import udp_commands
from config import config

# === DISABLE UNNECESSARY LOGS FOR TESTING ===
set_all_logs(False)
set_log_enabled("sensor.ultrasonic", True)
set_log_enabled("alarm.logic", True)
set_log_enabled("main", True)
# Communication debug for ESP-NOW/UDP
set_log_enabled("espnow_a", True)
set_log_enabled("communication.espnow", True)

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
    
    # Send initial message to Scheda B
    espnow_communication.send_message("Hello from Scheda A")

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
