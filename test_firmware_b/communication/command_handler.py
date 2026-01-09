"""Command handler for ESP32-B (Actuators).

Interprets and executes commands from any source (UDP, MQTT, HTTP, etc.).
Commands are transport-agnostic - this module only cares about command logic.

Supported commands:
- led <color> <state>: Control LED (green/blue/red, on/off/blinking)
- servo <angle>: Move servo to angle (0-180)
- lcd <line> <text>: Set LCD text (line1/line2)
- buzzer <state>: Control buzzer (on/off)
- audio <action> [track]: Audio control (play/pause/stop/volume/track)
- state: Get current actuator state
- status: Get system status
"""

from debug.debug import log
from core import state


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
        
        # LED control: led <color> <state>
        if command == "led":
            return _handle_led(args)
        
        # Servo control: servo <angle>
        elif command == "servo":
            return _handle_servo(args)
        
        # LCD control: lcd <line> <text...>
        elif command == "lcd":
            return _handle_lcd(args)
        
        # Buzzer control: buzzer <state>
        elif command == "buzzer":
            return _handle_buzzer(args)
        
        # Audio control: audio <action> [params]
        elif command == "audio":
            return _handle_audio(args)
        
        # Get current state: state
        elif command == "state":
            return _handle_state(args)
        
        # Get system status: status
        elif command == "status":
            return _handle_status(args)
        
        else:
            return {"success": False, "message": "Unknown command: {}".format(command)}
    
    except Exception as e:
        log("cmd_handler", "Error handling command '{}': {}".format(command, e))
        return {"success": False, "message": "Error: {}".format(e)}


def _handle_led(args):
    """Handle LED command: led <color> <state>"""
    if len(args) < 2:
        return {"success": False, "message": "Usage: led <color> <state>"}
    
    color = args[0].lower()
    mode = args[1].lower()
    
    if color not in ["green", "blue", "red"]:
        return {"success": False, "message": "Invalid color. Use: green, blue, red"}
    
    if mode not in ["on", "off", "blinking"]:
        return {"success": False, "message": "Invalid state. Use: on, off, blinking"}
    
    # Update state
    state.actuator_state["led_modes"][color] = mode
    state.actuator_state["leds"][color] = (mode == "on")  # Physical state
    
    log("cmd_handler", "LED {} set to {}".format(color, mode))
    return {"success": True, "message": "LED {} set to {}".format(color, mode)}


def _handle_servo(args):
    """Handle servo command: servo <angle>"""
    if len(args) < 1:
        return {"success": False, "message": "Usage: servo <angle>"}
    
    try:
        angle = int(args[0])
        if angle < 0 or angle > 180:
            return {"success": False, "message": "Angle must be 0-180"}
        
        state.actuator_state["servo"]["angle"] = angle
        state.actuator_state["servo"]["moving"] = True
        
        log("cmd_handler", "Servo set to {} degrees".format(angle))
        return {"success": True, "message": "Servo set to {} degrees".format(angle)}
    
    except ValueError:
        return {"success": False, "message": "Invalid angle. Must be integer 0-180"}


def _handle_lcd(args):
    """Handle LCD command: lcd <line> <text...>"""
    if len(args) < 2:
        return {"success": False, "message": "Usage: lcd <line> <text>"}
    
    line = args[0].lower()
    text = " ".join(args[1:])  # Join remaining args as text
    
    if line not in ["line1", "line2", "1", "2"]:
        return {"success": False, "message": "Invalid line. Use: line1, line2, 1, or 2"}
    
    # Normalize line names
    if line == "1":
        line = "line1"
    elif line == "2":
        line = "line2"
    
    # Truncate to 16 characters (LCD limit)
    text = text[:16]
    
    state.actuator_state["lcd"][line] = text
    
    log("cmd_handler", "LCD {} set to: {}".format(line, text))
    return {"success": True, "message": "LCD {} set to: {}".format(line, text)}


def _handle_buzzer(args):
    """Handle buzzer command: buzzer <state>"""
    if len(args) < 1:
        return {"success": False, "message": "Usage: buzzer <state>"}
    
    mode = args[0].lower()
    
    if mode not in ["on", "off"]:
        return {"success": False, "message": "Invalid state. Use: on, off"}
    
    state.actuator_state["buzzer"]["active"] = (mode == "on")
    
    log("cmd_handler", "Buzzer set to {}".format(mode))
    return {"success": True, "message": "Buzzer set to {}".format(mode)}


def _handle_audio(args):
    """Handle audio command: audio <action> [params]"""
    if len(args) < 1:
        return {"success": False, "message": "Usage: audio <play|pause|stop|volume|track> [params]"}
    
    action = args[0].lower()
    
    if action == "play":
        state.actuator_state["audio"]["playing"] = True
        state.actuator_state["audio"]["last_cmd"] = "play"
        log("cmd_handler", "Audio play")
        return {"success": True, "message": "Audio playing"}
    
    elif action == "pause":
        state.actuator_state["audio"]["playing"] = False
        state.actuator_state["audio"]["last_cmd"] = "pause"
        log("cmd_handler", "Audio pause")
        return {"success": True, "message": "Audio paused"}
    
    elif action == "stop":
        state.actuator_state["audio"]["playing"] = False
        state.actuator_state["audio"]["last_cmd"] = "stop"
        log("cmd_handler", "Audio stop")
        return {"success": True, "message": "Audio stopped"}
    
    elif action == "volume":
        if len(args) < 2:
            return {"success": False, "message": "Usage: audio volume <0-30>"}
        try:
            volume = int(args[1])
            if volume < 0 or volume > 30:
                return {"success": False, "message": "Volume must be 0-30"}
            state.actuator_state["audio"]["last_cmd"] = "volume:{}".format(volume)
            log("cmd_handler", "Audio volume set to {}".format(volume))
            return {"success": True, "message": "Volume set to {}".format(volume)}
        except ValueError:
            return {"success": False, "message": "Invalid volume"}
    
    elif action == "track":
        if len(args) < 2:
            return {"success": False, "message": "Usage: audio track <1-255>"}
        try:
            track = int(args[1])
            if track < 1 or track > 255:
                return {"success": False, "message": "Track must be 1-255"}
            state.actuator_state["audio"]["last_cmd"] = "track:{}".format(track)
            log("cmd_handler", "Audio track set to {}".format(track))
            return {"success": True, "message": "Track set to {}".format(track)}
        except ValueError:
            return {"success": False, "message": "Invalid track number"}
    
    else:
        return {"success": False, "message": "Invalid audio action. Use: play, pause, stop, volume, track"}


def _handle_state(args):
    """Handle state command: Get current actuator state"""
    response = {
        "success": True,
        "message": "Current actuator state",
        "state": state.actuator_state
    }
    log("cmd_handler", "State query")
    return response


def _handle_status(args):
    """Handle status command: Get system status"""
    from core import wifi
    
    status_info = {
        "wifi": "connected" if wifi.is_connected() else "disconnected",
        "simulation_mode": state.actuator_state.get("simulation_mode", False),
        "leds": state.actuator_state["led_modes"],
        "servo_angle": state.actuator_state["servo"]["angle"],
        "buzzer": "on" if state.actuator_state["buzzer"]["active"] else "off",
        "audio": "playing" if state.actuator_state["audio"]["playing"] else "stopped",
    }
    
    response = {
        "success": True,
        "message": "System status",
        "status": status_info
    }
    
    log("cmd_handler", "Status query")
    return response
