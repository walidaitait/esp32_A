"""Command handler for ESP32-A (Sensors).

Interprets and executes commands from any source (UDP, MQTT, HTTP, etc.).
Commands are transport-agnostic - this module only cares about command logic.

Supported commands:
- threshold <sensor> <value>: Set alarm threshold (temp/co/heart)
- simulate <sensor> <value>: Force simulated sensor value
- alarm <action>: Alarm control (trigger/clear/test)
- state: Get current sensor state
- status: Get system status
"""

from debug.debug import log
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
        
        # Alarm control: alarm <action>
        elif command == "alarm":
            return _handle_alarm(args)
        
        # Get current state: state
        elif command == "state":
            return _handle_state(args)
        
        # Get system status: status
        elif command == "status":
            return _handle_status(args)
        
        # Trigger OTA update: update
        elif command == "update":
            return _handle_update(args)
        
        # Trigger system reboot: reboot
        elif command == "reboot":
            return _handle_reboot(args)
        
        # Change simulation mode: mode <real|sim>
        elif command == "mode":
            return _handle_mode(args)
        
        else:
            return {"success": False, "message": "Unknown command: {}".format(command)}
    
    except Exception as e:
        log("cmd_handler", "Error handling command '{}': {}".format(command, e))
        return {"success": False, "message": "Error: {}".format(e)}


def _handle_threshold(args):
    """Handle threshold command: threshold <sensor> <value>"""
    if len(args) < 2:
        return {"success": False, "message": "Usage: threshold <sensor> <value>"}
    
    sensor = args[0].lower()
    
    try:
        value = float(args[1])
    except ValueError:
        return {"success": False, "message": "Invalid value. Must be a number"}
    
    # This is a placeholder - you would need to add threshold storage
    # to state.py and implement in alarm_logic.py
    log("cmd_handler", "Threshold {} set to {}".format(sensor, value))
    return {"success": True, "message": "Threshold {} set to {} (placeholder)".format(sensor, value)}


def _handle_simulate(args):
    """Handle simulate command: simulate <sensor> <value>"""
    if len(args) < 2:
        return {"success": False, "message": "Usage: simulate <sensor> <value>"}
    
    sensor = args[0].lower()
    value_str = args[1]
    
    # Parse value based on sensor type
    try:
        if sensor == "temperature" or sensor == "temp":
            value = float(value_str)
            state.sensor_data["temperature"] = value
            timers.mark_user_action("temp_read")
            log("cmd_handler", "Temperature simulated: {}°C".format(value))
            return {"success": True, "message": "Temperature set to {}°C".format(value)}
        
        elif sensor == "co":
            value = int(value_str)
            state.sensor_data["co"] = value
            timers.mark_user_action("co_read")
            log("cmd_handler", "CO simulated: {} ppm".format(value))
            return {"success": True, "message": "CO set to {} ppm".format(value)}
        
        elif sensor == "ultrasonic" or sensor == "distance":
            value = float(value_str)
            state.sensor_data["ultrasonic_distance_cm"] = value
            timers.mark_user_action("ultrasonic_read")
            log("cmd_handler", "Ultrasonic simulated: {} cm".format(value))
            return {"success": True, "message": "Distance set to {} cm".format(value)}
        
        elif sensor == "heart" or sensor == "bpm":
            value = int(value_str)
            if state.sensor_data["heart_rate"] is None:
                state.sensor_data["heart_rate"] = {}
            state.sensor_data["heart_rate"]["bpm"] = value
            timers.mark_user_action("heart_rate_read")
            log("cmd_handler", "Heart rate simulated: {} bpm".format(value))
            return {"success": True, "message": "Heart rate set to {} bpm".format(value)}
        
        elif sensor == "spo2":
            value = int(value_str)
            if state.sensor_data["heart_rate"] is None:
                state.sensor_data["heart_rate"] = {}
            state.sensor_data["heart_rate"]["spo2"] = value
            timers.mark_user_action("heart_rate_read")
            log("cmd_handler", "SpO2 simulated: {}%".format(value))
            return {"success": True, "message": "SpO2 set to {}%".format(value)}
        
        else:
            return {"success": False, "message": "Unknown sensor: {}".format(sensor)}
    
    except ValueError:
        return {"success": False, "message": "Invalid value for sensor {}".format(sensor)}


def _handle_alarm(args):
    """Handle alarm command: alarm <action>"""
    if len(args) < 1:
        return {"success": False, "message": "Usage: alarm <trigger|clear|test>"}
    
    action = args[0].lower()
    
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
    
    else:
        return {"success": False, "message": "Invalid action. Use: trigger, clear, test"}


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
    from core import wifi
    
    status_info = {
        "wifi": "connected" if wifi.is_connected() else "disconnected",
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
