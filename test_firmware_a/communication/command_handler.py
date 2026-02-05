"""Transport-agnostic command handler for ESP32-A (Sensor Board).

Imported by: communication.udp_commands, communication.nodered_client
Imports: debug.debug, core.state, core.timers

Interprets and executes commands from any source (UDP, MQTT, Node-RED, HTTP).
Commands are transport-agnostic - this module only handles command logic.

Supported commands:
- simulate <sensor> <value>: Force simulated sensor value
- test_alarm <warning|danger|reset>: Test alarm scenarios
- test_sensor <sensor> <action> [value]: Test specific sensor
- alarm <action>: Alarm control (trigger/clear/test)
- state: Get current sensor state
- status: Get system status
- log <channel> on/off: Control logging dynamically
- mode real/sim: Switch simulation mode
- update: Trigger OTA update
- reboot: Restart ESP32

All commands return: {\"success\": bool, \"message\": str, ...extra_data}
"""

from debug.debug import log, set_log_enabled, set_all_logs, get_log_flags
from core import state
from core import timers


def handle_command(command, args):
    """Handle a command with arguments.
    
    Args:
        command: Command name (string)
        args: List of command arguments (list of strings)
    
    Returns:
        dict: Response with 'success' (bool) and 'message' (string)
    """
    try:
        command = command.lower()
        
        # Threshold control: threshold <sensor> <value>
        if command == "threshold":
            return _handle_threshold(args)
        
        # Simulation control: simulate <sensor> <value>
        elif command == "simulate":
            return _handle_simulate(args)
        
        # Test alarm scenarios: test_alarm <warning|danger|reset>
        elif command == "test_alarm":
            return _handle_test_alarm(args)
        
        # Test specific sensor: test_sensor <sensor> <action> [value]
        elif command == "test_sensor":
            return _handle_test_sensor(args)
        
        # Alarm control: alarm <action>
        elif command == "alarm":
            return _handle_alarm(args)
        
        # Get current state: state
        elif command == "state":
            return _handle_state(args)
        
        # Get system status: status
        elif command == "status":
            return _handle_status(args)
        
        # Show active user locks: locks
        elif command == "locks":
            return _handle_locks(args)
        
        # Trigger OTA update: update
        elif command == "update":
            return _handle_update(args)
        
        # Trigger system reboot: reboot
        elif command == "reboot":
            return _handle_reboot(args)
        
        # Change simulation mode: mode <real|sim>
        elif command == "mode":
            return _handle_mode(args)

        # Logging control: log <channel|all|status> <on|off>
        elif command == "log":
            return _handle_log(args)
        
        else:
            return {"success": False, "message": "Unknown command: {}".format(command)}
    
    except Exception as e:
        log("cmd_handler", "Error handling command '{}': {}".format(command, e))
        return {"success": False, "message": "Error: {}".format(e)}


def _handle_log(args):
    """Handle log command: log <channel|all|status> <on|off>
    Examples:
      log espnow_a on
      log communication.espnow off
      log all off
      log status
    """
    if not args:
        return {"success": False, "message": "Usage: log <channel|all|status> <on|off>"}

    target = args[0].lower()

    # Status request
    if target == "status":
        return {"success": True, "message": "Log flags status", "log_flags": get_log_flags()}

    if len(args) < 2:
        return {"success": False, "message": "Usage: log <channel|all> <on|off>"}

    state = args[1].lower()
    if state in ("on", "true", "1"):
        enabled = True
    elif state in ("off", "false", "0"):
        enabled = False
    else:
        return {"success": False, "message": "Second arg must be on/off"}

    if target in ("all", "*"):
        set_all_logs(enabled)
        return {"success": True, "message": "All logs set to {}".format(enabled), "log_flags": get_log_flags()}

    set_log_enabled(target, enabled)
    return {
        "success": True,
        "message": "Log '{}' set to {}".format(target, enabled),
        "log_flags": get_log_flags(),
    }


def _handle_threshold(args):
    """Handle threshold command: threshold <sensor> <value>"""
    if len(args) < 2:
        return {"success": False, "message": "Usage: threshold <sensor> <value>"}
    
    # Args are already validated and normalized by send_command.py
    sensor = args[0]
    value = args[1]
    
    log("cmd_handler", "Threshold {} set to {}".format(sensor, value))
    return {"success": True, "message": "Threshold {} set to {} (placeholder)".format(sensor, value)}


def _handle_simulate(args):
    """Handle simulate command: simulate <sensor> <value>"""
    if len(args) < 2:
        return {"success": False, "message": "Usage: simulate <sensor> <value>"}
    
    # Args are already validated and normalized by send_command.py
    sensor = args[0]
    value_str = args[1]
    
    auto_value = value_str.lower() == "auto"

    # Parse value
    try:
        if sensor == "temperature":
            if auto_value:
                timers.clear_user_lock("temp_read")
                log("cmd_handler", "Temperature back to auto")
                return {"success": True, "message": "Temperature set to auto"}
            value = float(value_str)
            state.sensor_data["temperature"] = value
            timers.set_user_lock("temp_read")
            log("cmd_handler", "Temperature simulated: {}°C".format(value))
            return {"success": True, "message": "Temperature set to {}°C".format(value)}
        
        elif sensor == "co":
            if auto_value:
                timers.clear_user_lock("co_read")
                log("cmd_handler", "CO back to auto")
                return {"success": True, "message": "CO set to auto"}
            value = int(value_str)
            state.sensor_data["co"] = value
            timers.set_user_lock("co_read")
            log("cmd_handler", "CO simulated: {} ppm".format(value))
            return {"success": True, "message": "CO set to {} ppm".format(value)}
        
        elif sensor == "ultrasonic":
            if auto_value:
                timers.clear_user_lock("ultrasonic_read")
                log("cmd_handler", "Ultrasonic back to auto")
                return {"success": True, "message": "Ultrasonic set to auto"}
            value = float(value_str)
            state.sensor_data["ultrasonic_distance_cm"] = value
            timers.set_user_lock("ultrasonic_read")
            log("cmd_handler", "Ultrasonic simulated: {} cm".format(value))
            return {"success": True, "message": "Distance set to {} cm".format(value)}
        
        elif sensor == "heart":
            if auto_value:
                timers.clear_user_lock("heart_rate_read")
                log("cmd_handler", "Heart rate back to auto")
                return {"success": True, "message": "Heart rate set to auto"}
            value = int(value_str)
            if state.sensor_data["heart_rate"] is None:
                state.sensor_data["heart_rate"] = {}
            state.sensor_data["heart_rate"]["bpm"] = value
            timers.set_user_lock("heart_rate_read")
            log("cmd_handler", "Heart rate simulated: {} bpm".format(value))
            return {"success": True, "message": "Heart rate set to {} bpm".format(value)}
        
        elif sensor == "spo2":
            if auto_value:
                timers.clear_user_lock("heart_rate_read")
                log("cmd_handler", "SpO2 back to auto")
                return {"success": True, "message": "SpO2 set to auto"}
            value = int(value_str)
            if state.sensor_data["heart_rate"] is None:
                state.sensor_data["heart_rate"] = {}
            state.sensor_data["heart_rate"]["spo2"] = value
            timers.set_user_lock("heart_rate_read")
            log("cmd_handler", "SpO2 simulated: {}%".format(value))
            return {"success": True, "message": "SpO2 set to {}%".format(value)}
        
        else:
            return {"success": False, "message": "Unknown sensor: {}".format(sensor)}
    
    except ValueError:
        return {"success": False, "message": "Invalid value for sensor {}".format(sensor)}


def _handle_test_alarm(args):
    """Handle test_alarm command: test_alarm <warning|danger|reset>
    
    Simulates alarm scenarios by setting sensor values to trigger specific alarm levels.
    """
    if len(args) < 1:
        return {"success": False, "message": "Usage: test_alarm <warning|danger|reset>"}
    
    action = args[0].lower()
    
    if action == "warning":
        # Trigger warning: CO just above warning threshold but below danger
        state.sensor_data["co"] = 60  # Above critical (50 PPM) by 10
        timers.set_user_lock("co_read")
        log("cmd_handler", "TEST: CO set to 60 ppm -> should trigger WARNING in ~5 seconds")
        return {
            "success": True,
            "message": "Alarm TEST: Warning scenario activated. CO set to 60 ppm. Should reach WARNING state in ~5 seconds."
        }
    
    elif action == "danger":
        # Trigger danger: CO well above threshold
        state.sensor_data["co"] = 120  # Well above critical
        timers.set_user_lock("co_read")
        log("cmd_handler", "TEST: CO set to 120 ppm -> should trigger DANGER in ~30 seconds")
        return {
            "success": True,
            "message": "Alarm TEST: Danger scenario activated. CO set to 120 ppm. Should reach DANGER state in ~30 seconds."
        }
    
    elif action == "reset":
        # Reset to safe value
        state.sensor_data["co"] = 10
        state.sensor_data["temperature"] = 23.5
        state.sensor_data["heart_rate"]["bpm"] = 75
        state.sensor_data["heart_rate"]["spo2"] = 98
        timers.set_user_lock("co_read")
        timers.set_user_lock("temp_read")
        timers.set_user_lock("heart_rate_read")
        log("cmd_handler", "TEST: All sensors reset to safe values")
        return {
            "success": True,
            "message": "Alarm TEST: All sensors reset to safe values. Alarm should recover to NORMAL within recovery times."
        }
    
    else:
        return {"success": False, "message": "Invalid test_alarm action. Use: warning, danger, reset"}


def _handle_test_sensor(args):
    """Handle test_sensor command: test_sensor <sensor> <action> [value]
    
    Test individual sensors without triggering full alarm logic.
    Actions: set <value>, min, max, normal
    """
    if len(args) < 2:
        return {"success": False, "message": "Usage: test_sensor <sensor> <action> [value]"}
    
    sensor = args[0].lower()
    action = args[1].lower()
    
    try:
        if sensor == "co":
            if action == "set" and len(args) >= 3:
                value = int(args[2])
                state.sensor_data["co"] = value
                timers.set_user_lock("co_read")
                log("cmd_handler", "TEST: CO sensor set to {} ppm".format(value))
                return {"success": True, "message": "CO set to {} ppm".format(value)}
            elif action == "min":
                state.sensor_data["co"] = 0
                timers.set_user_lock("co_read")
                return {"success": True, "message": "CO set to minimum (0 ppm)"}
            elif action == "max":
                state.sensor_data["co"] = 200
                timers.set_user_lock("co_read")
                return {"success": True, "message": "CO set to maximum (200 ppm)"}
            elif action == "normal":
                state.sensor_data["co"] = 10
                timers.set_user_lock("co_read")
                return {"success": True, "message": "CO set to normal (10 ppm)"}
            else:
                return {"success": False, "message": "CO actions: set <ppm>, min, max, normal"}
        
        elif sensor == "temperature":
            if action == "set" and len(args) >= 3:
                value = float(args[2])
                state.sensor_data["temperature"] = value
                timers.set_user_lock("temp_read")
                log("cmd_handler", "TEST: Temperature set to {}°C".format(value))
                return {"success": True, "message": "Temperature set to {}°C".format(value)}
            elif action == "min":
                state.sensor_data["temperature"] = 5  # Below safe min (10°C)
                timers.set_user_lock("temp_read")
                return {"success": True, "message": "Temperature set to minimum (5°C - UNSAFE)"}
            elif action == "max":
                state.sensor_data["temperature"] = 40  # Above safe max (35°C)
                timers.set_user_lock("temp_read")
                return {"success": True, "message": "Temperature set to maximum (40°C - UNSAFE)"}
            elif action == "normal":
                state.sensor_data["temperature"] = 23.5
                timers.mark_user_action("temp_read")
                return {"success": True, "message": "Temperature set to normal (23.5°C)"}
            else:
                return {"success": False, "message": "Temperature actions: set <°C>, min, max, normal"}
        
        elif sensor == "heart" or sensor == "hr":
            if action == "set" and len(args) >= 3:
                value = int(args[2])
                if state.sensor_data["heart_rate"] is None:
                    state.sensor_data["heart_rate"] = {}
                state.sensor_data["heart_rate"]["bpm"] = value
                timers.mark_user_action("heart_rate_read")
                log("cmd_handler", "TEST: Heart rate set to {} bpm".format(value))
                return {"success": True, "message": "Heart rate set to {} bpm".format(value)}
            elif action == "low":
                if state.sensor_data["heart_rate"] is None:
                    state.sensor_data["heart_rate"] = {}
                state.sensor_data["heart_rate"]["bpm"] = 40  # Below safe min (50 bpm)
                timers.mark_user_action("heart_rate_read")
                return {"success": True, "message": "Heart rate set to low (40 bpm - UNSAFE)"}
            elif action == "high":
                if state.sensor_data["heart_rate"] is None:
                    state.sensor_data["heart_rate"] = {}
                state.sensor_data["heart_rate"]["bpm"] = 140  # Above safe max (120 bpm)
                timers.mark_user_action("heart_rate_read")
                return {"success": True, "message": "Heart rate set to high (140 bpm - UNSAFE)"}
            elif action == "normal":
                if state.sensor_data["heart_rate"] is None:
                    state.sensor_data["heart_rate"] = {}
                state.sensor_data["heart_rate"]["bpm"] = 75
                timers.mark_user_action("heart_rate_read")
                return {"success": True, "message": "Heart rate set to normal (75 bpm)"}
            else:
                return {"success": False, "message": "Heart rate actions: set <bpm>, low, high, normal"}
        
        else:
            return {"success": False, "message": "Unknown sensor: {}. Available: co, temperature, heart".format(sensor)}
    
    except (ValueError, TypeError):
        return {"success": False, "message": "Invalid value format for {}".format(sensor)}


def _handle_alarm(args):
    """Handle alarm command: alarm <action>"""
    if len(args) < 1:
        return {"success": False, "message": "Usage: alarm <trigger|clear|test>"}
    
    # Args are already validated and normalized by send_command.py
    action = args[0]
    
    if action == "trigger":
        state.alarm_state["level"] = "danger"
        state.alarm_state["source"] = "manual"
        log("cmd_handler", "Alarm triggered manually")
        return {"success": True, "message": "Alarm triggered"}
    
    elif action == "clear":
        state.alarm_state["level"] = "normal"
        state.alarm_state["source"] = None
        log("cmd_handler", "Alarm cleared")
        return {"success": True, "message": "Alarm cleared"}
    
    elif action == "test":
        log("cmd_handler", "Alarm test")
        return {
            "success": True,
            "message": "Alarm test",
            "alarm": state.alarm_state
        }


def _handle_state(args):
    """Handle state command: Get current sensor state"""
    response = {
        "success": True,
        "message": "Current sensor state",
        "state": {
            "sensors": state.sensor_data,
            "buttons": state.button_state,
            "alarm": state.alarm_state,
            "system": state.system_state
        }
    }
    log("cmd_handler", "State query")
    return response


def _handle_status(args):
    """Handle status command: Get system status"""
    from communication import wifi
    from config.config import FIRMWARE_VERSION
    
    status_info = {
        "firmware_version": FIRMWARE_VERSION,
        "wifi": "connected" if wifi.is_connected() else "disconnected",
        "simulation_mode": state.simulation_mode,
        "alarm_level": state.alarm_state["level"],
        "alarm_source": state.alarm_state["source"],
        "temperature": state.sensor_data.get("temperature"),
        "co": state.sensor_data.get("co"),
        "heart_bpm": state.sensor_data.get("heart_rate", {}).get("bpm") if state.sensor_data.get("heart_rate") else None,
    }
    
    response = {
        "success": True,
        "message": "System status",
        "status": status_info
    }
    
    log("cmd_handler", "Status query")
    return response


def _handle_locks(args):
    """Handle locks command: Show active user locks"""
    from core.timers import _user_actions
    
    if not _user_actions:
        return {"success": True, "message": "No active locks"}
    
    locks_list = ", ".join(_user_actions.keys())
    response = {
        "success": True,
        "message": "Active user locks: {}".format(locks_list),
        "locks": list(_user_actions.keys())
    }
    
    log("cmd_handler", "Locks query: {}".format(locks_list))
    return response


def _handle_update(args):
    """Handle update command: Set OTA flag and reboot"""
    import json
    import machine  # type: ignore
    
    log("cmd_handler", "OTA update requested via command")
    
    try:
        # Try to load existing config
        try:
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
        except:
            try:
                with open("config.json", "r") as f:
                    config_data = json.load(f)
            except:
                config_data = {}
        
        # Set OTA update flag
        config_data["ota_update_pending"] = True
        
        # Write back to config.json
        try:
            with open("config/config.json", "w") as f:
                json.dump(config_data, f)
        except:
            with open("config.json", "w") as f:
                json.dump(config_data, f)
        
        log("cmd_handler", "OTA update flag set - rebooting")
        
        # Reboot to trigger OTA update on startup
        import time  # type: ignore
        time.sleep(1)
        machine.reset()
        
        return {
            "success": True,
            "message": "OTA update will start after reboot."
        }
    except Exception as e:
        log("cmd_handler", "Error setting OTA flag: {}".format(e))
        return {
            "success": False,
            "message": "Error setting OTA flag: {}".format(e)
        }


def _handle_reboot(args):
    """Handle reboot command: Trigger system reboot"""
    state.system_control["reboot_requested"] = True
    log("cmd_handler", "System reboot requested via command")
    return {
        "success": True,
        "message": "System will reboot shortly."
    }


def _handle_mode(args):
    """Handle mode command: mode <real|sim>"""
    import json
    
    if len(args) < 1:
        return {"success": False, "message": "Usage: mode <real|sim>"}
    
    mode = args[0].lower()
    
    if mode not in ["real", "sim", "simulation"]:
        return {"success": False, "message": "Invalid mode. Use: real, sim"}
    
    simulate = (mode in ["sim", "simulation"])
    
    # Save mode to config.json
    try:
        # Try to load existing config
        try:
            with open("config/config.json", "r") as f:
                config_data = json.load(f)
        except:
            try:
                with open("config.json", "r") as f:
                    config_data = json.load(f)
            except:
                config_data = {}
        
        # Update simulate_sensors field
        config_data["simulate_sensors"] = simulate
        
        # Write back to config.json
        try:
            with open("config/config.json", "w") as f:
                json.dump(config_data, f)
        except:
            with open("config.json", "w") as f:
                json.dump(config_data, f)
        
        log("cmd_handler", "Mode changed to: {}".format("simulation" if simulate else "real"))
        
        # Request reboot
        state.system_control["reboot_requested"] = True
        
        return {
            "success": True,
            "message": "Mode set to {}. System will reboot.".format("simulation" if simulate else "real")
        }
    except Exception as e:
        return {"success": False, "message": "Error saving mode: {}".format(e)}
