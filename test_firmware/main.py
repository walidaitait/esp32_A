"""Main loop: sensor reading + alarm logic.

Clean version without verbose test prints.
- Performs only:
  * sensor initialization with debug logs
  * continuous sensor reading
  * alarm logic evaluation
  * compact sensor + system status debug every 2.5 seconds
"""

# Import OTA first
import ota_update
ota_update.check_and_update()

import time
from debug import log, init_remote_logging
import state
from logic.alarm_logic import evaluate_logic
from timers import elapsed
from comms import command_sender

# Sensor modules
from sensors import temperature, co, ultrasonic, heart_rate, buttons


DEBUG_INTERVAL_MS = 2500
_last_debug = 0


def init_sensors():
    """Initialize all sensors and communication system."""
    log("main", "init_sensors: Initializing sensors...")

    sensors_status = {
        "temperature": temperature.init_temperature(),
        "co": co.init_co(),
        "ultrasonic": ultrasonic.init_ultrasonic(),
        "heart_rate": heart_rate.init_heart_rate(),
        "buttons": buttons.init_buttons(),
    }

    for name, ok in sensors_status.items():
        log("main", "init_sensors: {} -> {}".format(name, "OK" if ok else "FAILED"))
    
    # Initialize communication system
    log("main", "init_sensors: Initializing communication with ESP32-B...")
    comm_ok = command_sender.init()
    log("main", "init_sensors: Communication -> {}".format("OK" if comm_ok else "FAILED"))

    return sensors_status


def read_sensors():
    """Non-blocking read of all sensors."""
    temperature.read_temperature()
    co.read_co()
    ultrasonic.read_ultrasonic()
    heart_rate.read_heart_rate()
    buttons.read_buttons()


def _compact_state_snapshot():
    """Returns a compact string with sensors + system state."""
    temp = state.sensor_data.get("temperature")
    co_val = state.sensor_data.get("co")
    dist = state.sensor_data.get("ultrasonic_distance_cm")
    hr = state.sensor_data.get("heart_rate", {})

    alarm_level = state.alarm_state.get("level", "normal")
    alarm_src = state.alarm_state.get("source")

    parts = []
    parts.append("T={:.1f}C".format(temp) if temp is not None else "T=N/A")
    parts.append("CO={:.1f}ppm".format(co_val) if co_val is not None else "CO=N/A")
    parts.append("D={:.0f}cm".format(dist) if dist is not None else "D=N/A")

    bpm = hr.get("bpm")
    spo2 = hr.get("spo2")
    if bpm is not None:
        parts.append("HR={}bpm".format(bpm))
    if spo2 is not None:
        parts.append("SpO2={}%%".format(spo2))

    parts.append("ALARM={}({})".format(alarm_level, alarm_src))

    return " | ".join(parts)


def periodic_debug():
    """Compact log of sensors + state every DEBUG_INTERVAL_MS."""
    global _last_debug
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_debug) < DEBUG_INTERVAL_MS:
        return

    _last_debug = now
    snapshot = _compact_state_snapshot()
    log("main", "periodic_debug: {}".format(snapshot))


def main():
    log("main", "main: Boot main loop")
    
    # Initialize remote logging (for centralized monitoring)
    log("main", "main: Initializing remote UDP logging...")
    init_remote_logging('A')  # 'A' for ESP32-A

    init_sensors()

    while True:
        try:
            read_sensors()
            evaluate_logic()
            periodic_debug()
            
            # Non-blocking communication update
            command_sender.update()
            
            # Log connection status periodically
            if elapsed("comm_status", 5000):
                if command_sender.is_connected():
                    log("main", "main: ESP32-B: CONNECTED - sending commands")
                else:
                    log("main", "main: ESP32-B: DISCONNECTED - retrying connection...")
            
            # TEST: Send test command every 1 second
            if elapsed("test_command", 1000):
                if command_sender.is_connected():
                    # Send test display message with timestamp
                    command_sender.send_display_message(
                        "Test A->B",
                        "Time: {}".format(time.ticks_ms() // 1000)
                    )
            
            # Use non-blocking timing instead of sleep
            if elapsed("main_loop", 10):
                pass
                
        except KeyboardInterrupt:
            log("main", "main: Loop interrupted by user")
            break
        except Exception as e:
            log("main", "main: Exception: {}".format(e))
            # Use non-blocking wait instead of blocking sleep
            if elapsed("error_recovery", 1000):
                pass


if __name__ == "__main__":
    main()
