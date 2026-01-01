"""Command handler for ESP32-B - executes commands from ESP32-A.

Receives commands via comm.py and executes them on actuators:
- Alarm level changes (LED, buzzer, servo, LCD, audio)
- Display messages
- Direct actuator control

All actuator control logic is centralized here.
"""

from debug.debug import log
from comms import comm
from core import state

# Import actuators (will be used when executing commands)
from actuators import leds, servo, lcd, buzzer, audio


# ===========================
# ALARM STATE MAPPING
# ===========================

# Alarm level to LED color mapping
ALARM_LED_MAP = {
    "normal": {"red": False, "green": True, "blue": False},   # Green
    "warning": {"red": True, "green": True, "blue": False},   # Yellow (red+green)
    "danger": {"red": True, "green": False, "blue": False},   # Red
}

# Alarm level to servo position mapping (degrees)
ALARM_SERVO_MAP = {
    "normal": 0,    # Fully closed
    "warning": 90,  # Half open
    "danger": 180,  # Fully open
}

# Alarm level to buzzer pattern mapping
ALARM_BUZZER_MAP = {
    "normal": None,         # Off
    "warning": "beep",      # Beep pattern
    "danger": "continuous", # Continuous sound
}

# Alarm level to audio track mapping
ALARM_AUDIO_MAP = {
    "normal": None,
    "warning": 1,   # Track 1 for warning
    "danger": 2,    # Track 2 for danger
}


# ===========================
# COMMAND EXECUTION
# ===========================

def _execute_set_alarm_level(params):
    """Execute alarm level change command.
    
    Updates all actuators based on alarm level:
    - LEDs: Green (normal), Yellow (warning), Red (danger)
    - Servo: 0° (normal), 90° (warning), 180° (danger)
    - Buzzer: Off (normal), Beep (warning), Continuous (danger)
    - Audio: Off (normal), Track 1 (warning), Track 2 (danger)
    - LCD: Display alarm status
    
    Args:
        params: {"level": "normal"|"warning"|"danger", "source": "co"|"temp"|...}
    """
    level = params.get("level", "normal")
    source = params.get("source", "unknown")
    
    log("cmd_handler", "Alarm level: {} (source: {})".format(level, source))
    
    # Update state
    state.communication_state["alarm_level"] = level
    state.communication_state["alarm_source"] = source
    
    # Update LEDs
    led_states = ALARM_LED_MAP.get(level, ALARM_LED_MAP["normal"])
    leds.set_led("red", led_states["red"])
    leds.set_led("green", led_states["green"])
    leds.set_led("blue", led_states["blue"])
    
    # Update servo
    servo_angle = ALARM_SERVO_MAP.get(level, 0)
    servo.set_servo_angle(servo_angle)
    
    # Update buzzer
    buzzer_pattern = ALARM_BUZZER_MAP.get(level)
    if buzzer_pattern:
        buzzer.set_pattern(buzzer_pattern)
    else:
        buzzer.stop()
    
    # Update audio
    audio_track = ALARM_AUDIO_MAP.get(level)
    if audio_track:
        audio.play(audio_track)
    else:
        audio.stop()
    
    # Update LCD
    line1 = "Alarm: {}".format(level.upper())
    line2 = "Source: {}".format(source[:16])
    lcd.display(line1, line2)


def _execute_display_message(params):
    """Execute display message command.
    
    Args:
        params: {"line1": "text", "line2": "text"}
    """
    line1 = params.get("line1", "")
    line2 = params.get("line2", "")
    
    log("cmd_handler", "Display: '{}' | '{}'".format(line1, line2))
    
    lcd.display(line1, line2)


def _execute_set_led(params):
    """Execute LED control command.
    
    Args:
        params: {"color": "red"|"green"|"blue", "state": true|false}
    """
    color = params.get("color")
    state_on = params.get("state", False)
    
    log("cmd_handler", "LED {}: {}".format(color, "ON" if state_on else "OFF"))
    
    leds.set_led(color, state_on)


def _execute_move_servo(params):
    """Execute servo movement command.
    
    Args:
        params: {"angle": 0-180}
    """
    angle = params.get("angle", 0)
    
    log("cmd_handler", "Servo: {}°".format(angle))
    
    servo.set_servo_angle(angle)


def _execute_set_buzzer(params):
    """Execute buzzer control command.
    
    Args:
        params: {"pattern": "off"|"beep"|"continuous"|..., "duration_ms": int}
    """
    pattern = params.get("pattern", "off")
    duration_ms = params.get("duration_ms")
    
    log("cmd_handler", "Buzzer: {}".format(pattern))
    
    if pattern == "off":
        buzzer.stop()
    else:
        buzzer.set_pattern(pattern)
        if duration_ms:
            # TODO: implement duration (needs timer in buzzer module)
            pass


def _execute_control_audio(params):
    """Execute audio control command.
    
    Args:
        params: {"action": "play"|"stop"|..., "track": int, "volume": int}
    """
    action = params.get("action")
    track = params.get("track")
    volume = params.get("volume")
    
    log("cmd_handler", "Audio: {} (track={}, vol={})".format(action, track, volume))
    
    if volume is not None:
        audio.set_volume(volume)
    
    if action == "play" and track is not None:
        audio.play(track)
    elif action == "stop":
        audio.stop()
    elif action == "pause":
        audio.pause()
    elif action == "resume":
        audio.resume()
    elif action == "next":
        audio.next_track()
    elif action == "prev":
        audio.prev_track()


# ===========================
# COMMAND DISPATCHER
# ===========================

# Command name to handler function mapping
COMMAND_HANDLERS = {
    "set_alarm_level": _execute_set_alarm_level,
    "display_message": _execute_display_message,
    "set_led": _execute_set_led,
    "move_servo": _execute_move_servo,
    "set_buzzer": _execute_set_buzzer,
    "control_audio": _execute_control_audio,
}


def _handle_command(command, params):
    """Handle received command by dispatching to appropriate handler.
    
    Args:
        command: Command name string
        params: Command parameters dict
    """
    handler = COMMAND_HANDLERS.get(command)
    
    if handler:
        try:
            handler(params)
        except Exception as e:
            log("cmd_handler", "ERROR executing '{}': {}".format(command, e))
    else:
        log("cmd_handler", "ERROR: Unknown command '{}'".format(command))


# ===========================
# INITIALIZATION
# ===========================

def init():
    """Initialize command handler and register with comm.py."""
    # Initialize communication system
    if not comm.init_communication():
        return False
    
    # Register command callback
    comm.register_command_callback(_handle_command)
    
    log("cmd_handler", "Command handler initialized")
    return True


def update():
    """Update communication system (delegates to comm.py)."""
    comm.update()


def is_connected():
    """Check if ESP32-A is connected (delegates to comm.py)."""
    return comm.is_connected()
