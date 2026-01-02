"""Command sender for ESP32-A → ESP32-B communication.

Handles high-level command logic:
- send_alarm_command(level, source): Notify B of alarm state changes
- send_display_message(text): Show message on LCD
- send_led_control(color, state): Control LED
- send_servo_position(angle): Move servo
- send_buzzer_command(pattern): Control buzzer

All commands are sent through comm.py low-level interface.
"""

from debug.debug import log
from comms import comm


# ===========================
# ALARM COMMANDS
# ===========================

def send_alarm_command(level, source=None):
    """Send alarm level change command to ESP32-B.
    
    Args:
        level: "normal", "warning", or "danger"
        source: Optional source of alarm (e.g., "co", "temp", "heart")
        
    Returns:
        True if command sent successfully
    """
    payload = {
        "command": "set_alarm_level",
        "params": {
            "level": level,
            "source": source
        }
    }
    
    success = comm.send_data(payload)
    
    if success:
        log("cmd_sender", "Alarm command sent: {} ({})".format(level, source))
    else:
        log("cmd_sender", "Failed to send alarm command")
    
    return success


# ===========================
# DISPLAY COMMANDS
# ===========================

def send_display_message(line1="", line2=""):
    """Send display message command to ESP32-B LCD.
    
    Args:
        line1: First line of text (up to 16 chars)
        line2: Second line of text (up to 16 chars)
        
    Returns:
        True if command sent successfully
    """
    payload = {
        "command": "display_message",
        "params": {
            "line1": line1[:16],  # Truncate to LCD width
            "line2": line2[:16]
        }
    }
    
    success = comm.send_data(payload)
    
    if success:
        log("cmd_sender", "Display command sent: '{}' | '{}'".format(line1, line2))
    
    return success


# ===========================
# LED COMMANDS
# ===========================

def send_led_control(color, state):
    """Send LED control command to ESP32-B.
    
    Args:
        color: "red", "green", or "blue"
        state: True (on) or False (off)
        
    Returns:
        True if command sent successfully
    """
    payload = {
        "command": "set_led",
        "params": {
            "color": color,
            "state": state
        }
    }
    
    success = comm.send_data(payload)
    
    if success:
        log("cmd_sender", "LED command sent: {} = {}".format(color, "ON" if state else "OFF"))
    
    return success


# ===========================
# SERVO COMMANDS
# ===========================

def send_servo_position(angle):
    """Send servo position command to ESP32-B.
    
    Args:
        angle: Servo angle in degrees (0-180)
        
    Returns:
        True if command sent successfully
    """
    # Clamp angle to valid range
    angle = max(0, min(180, angle))
    
    payload = {
        "command": "move_servo",
        "params": {
            "angle": angle
        }
    }
    
    success = comm.send_data(payload)
    
    if success:
        log("cmd_sender", "Servo command sent: {}°".format(angle))
    
    return success


# ===========================
# BUZZER COMMANDS
# ===========================

def send_buzzer_command(pattern, duration_ms=None):
    """Send buzzer control command to ESP32-B.
    
    Args:
        pattern: "off", "beep", "continuous", "warning", "danger"
        duration_ms: Optional duration in milliseconds
        
    Returns:
        True if command sent successfully
    """
    payload = {
        "command": "set_buzzer",
        "params": {
            "pattern": pattern,
            "duration_ms": duration_ms
        }
    }
    
    success = comm.send_data(payload)
    
    if success:
        log("cmd_sender", "Buzzer command sent: {}".format(pattern))
    
    return success


# ===========================
# AUDIO COMMANDS
# ===========================

def send_audio_command(action, track=None, volume=None):
    """Send DFPlayer audio command to ESP32-B.
    
    Args:
        action: "play", "stop", "pause", "resume", "next", "prev"
        track: Track number (1-255) if action is "play"
        volume: Volume level (0-30) if provided
        
    Returns:
        True if command sent successfully
    """
    payload = {
        "command": "control_audio",
        "params": {
            "action": action,
            "track": track,
            "volume": volume
        }
    }
    
    success = comm.send_data(payload)
    
    if success:
        log("cmd_sender", "Audio command sent: {} (track={}, vol={})".format(
            action, track, volume))
    
    return success


# ===========================
# INITIALIZATION
# ===========================

def init():
    """Initialize command sender (delegates to comm.py)."""
    return comm.init_communication()


def update():
    """Update communication system (delegates to comm.py)."""
    comm.update()


def is_connected():
    """Check if ESP32-B is connected (delegates to comm.py)."""
    return comm.is_connected()
