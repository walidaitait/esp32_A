"""SG90 9g Servo motor driver for ESP32-B automatic gate control.

Imported by: core.actuator_loop
Imports: machine (Pin, PWM), time, config.config, core.state, debug.debug

Controls SG90 servo for automatic gate opening/closing based on:
1. Presence detection from ultrasonic sensor (Board A)
2. Alarm level from alarm logic (Board A)

Gate automation logic (SECURITY ENHANCED):
- presence_detected=True + alarm_level="danger" → Open gate (180°)
- presence lost for 5s → Close gate (0°)
- Manual control via commands overrides automation temporarily

SECURITY: Gate only opens automatically in "danger" mode to prevent
unauthorized entry (e.g., burglar triggering ultrasonic sensor).

Servo control features:
- Immediate motion: Servo moves instantly to target angle
- PWM parameters: 50Hz, 0.5-2.5ms pulse width, 0-180° range

Hardware: SG90 servo on GPIO configured in config.SERVO_PIN
"""
from machine import Pin, PWM  # type: ignore
from time import ticks_ms, ticks_diff, sleep_ms  # type: ignore
from config import config
from core import state
from core.timers import elapsed
from debug.debug import log

_pwm = None
_angle = 0
_initialized = False

# Gate automation state (received from ESP32-A)
_presence_detected = False
_gate_open = False
_presence_lost_time_ms = None

# Button B1 toggle tracking
_last_button_b1_state = False  # Track previous button state to detect press event

# Movement protection and command queue
_last_command_time_ms = 0  # Track last command execution time
_command_queue = []  # Queue for pending servo commands: [(angle, source_info), ...]
_MIN_COMMAND_INTERVAL_MS = 1000  # Minimum time between command executions (reduced from 2500ms)

# Typical PWM parameters for servo: 50Hz, pulse 0.5-2.5ms
_PWM_FREQ = 50
_MIN_US = 500
_MAX_US = 2500
_PERIOD_US = 1000000 // _PWM_FREQ
_MAX_DUTY = 1023


def _angle_to_duty(angle):
    # Map 0-180° to 10-bit duty (0-1023)
    angle = max(0, min(180, angle))
    pulse_us = _MIN_US + ((_MAX_US - _MIN_US) * angle) // 180
    duty_10bit = (_MAX_DUTY * pulse_us) // _PERIOD_US
    # Convert to 16-bit for duty_u16()
    duty_16bit = duty_10bit * 64
    return duty_16bit


def _set_angle_immediate(angle):
    """Set servo angle directly (internal use)."""
    global _angle
    if _pwm is None:
        return
    
    old_angle = _angle
    _angle = max(0, min(config.SERVO_MAX_ANGLE, angle))
    
    # Log only if angle actually changes to detect repeated commands
    if old_angle != _angle:
        log("actuator.servo.debug", "PWM: {}° → {}°".format(old_angle, _angle))
    
    try:
        duty_val = _angle_to_duty(_angle)
        _pwm.duty_u16(duty_val)
        state.actuator_state["servo"]["angle"] = _angle
    except Exception as e:
        log("actuator.servo", "Set angle error: {}".format(e))


def _execute_servo_command(angle, source):
    """Execute a servo command immediately (internal use).
    
    Updates hardware, timestamp, and locks automation.
    """
    global _last_command_time_ms
    
    old_angle = _angle
    _set_angle_immediate(angle)
    _last_command_time_ms = ticks_ms()
    
    # Reset movement timer to lock automation for 1000ms
    elapsed("servo_movement", 0)
    
    log("actuator.servo", "Servo: {}° → {}° from {} (automation LOCKED for {}ms)".format(
        old_angle, angle, source, _MIN_COMMAND_INTERVAL_MS))


def set_servo_angle_immediate(angle, source="unknown"):
    """Set servo angle instantly - single PWM command, no intermediate steps.
    
    If called too soon after previous command, enqueues the command instead of ignoring it.
    Commands are processed sequentially from the queue.
    
    Args:
        angle: Target angle (0-180)
        source: Command source for logging ("app", "automation", "button", etc.)
    """
    global _last_command_time_ms, _command_queue
    
    if _pwm is None:
        log("actuator.servo", "set_servo_angle_immediate ignored (PWM not initialized)")
        return

    angle = max(0, min(config.SERVO_MAX_ANGLE, angle))
    now = ticks_ms()
    
    # Check if we can execute immediately
    time_since_last = ticks_diff(now, _last_command_time_ms) if _last_command_time_ms > 0 else 9999
    can_execute_now = time_since_last >= _MIN_COMMAND_INTERVAL_MS
    
    # Check if command is redundant (same angle as current)
    if angle == _angle:
        log("actuator.servo.debug", "Servo already at {}° (redundant from {})".format(angle, source))
        return
    
    # If we can execute now and queue is empty, execute immediately
    if can_execute_now and not _command_queue:
        _execute_servo_command(angle, source)
    else:
        # Otherwise, enqueue the command
        _command_queue.append((angle, source))
        log("actuator.servo", "Servo command QUEUED: {}° from {} (wait {}ms, queue size: {})".format(
            angle, source, _MIN_COMMAND_INTERVAL_MS - time_since_last, len(_command_queue)))


def init_servo():
    global _pwm, _angle, _initialized
    log("actuator.servo", "init_servo() called")
    try:
        servo_pin = config.SERVO_PIN
        log("actuator.servo", "init_servo: SERVO_PIN={}".format(servo_pin))
        pin = Pin(servo_pin, Pin.OUT)
        log("actuator.servo", "init_servo: Pin object created")
        _pwm = PWM(pin, freq=_PWM_FREQ)
        log("actuator.servo", "init_servo: PWM created freq={}Hz, PWM object={}".format(_PWM_FREQ, _pwm))

        # Start always at 0°
        _angle = 0
        state.actuator_state["servo"]["angle"] = 0

        # Mark initialized before first duty set so guard does not block
        _initialized = True
        log("actuator.servo", "init_servo: setting initial position to 0°")
        _set_angle_immediate(_angle)
        
        log("actuator.servo", "Servo initialized at 0°")
        return True
    except Exception as e:
        log("actuator.servo", "Initialization failed: {}".format(e))
        import traceback
        log("actuator.servo", "Traceback: {}".format(traceback.format_exc()))
        _pwm = None
        _initialized = False
        return False


def _check_button_b1_toggle():
    """Check if button B1 was pressed and toggle gate state.
    
    Detects press event (transition from False to True) and toggles gate open/closed.
    Compatible with automatic gate control and app commands.
    
    NOTE: Button press detection requires release between presses (False -> True -> False required).
    """
    global _gate_open, _last_button_b1_state
    
    # Get current button state from received sensor data (from Board A)
    current_button_state = state.received_sensor_state.get("button_b1", False)
    
    # Detect press event: transition from False to True
    # This requires that the button was released (False) before being pressed again (True)
    if current_button_state and not _last_button_b1_state:
        log("actuator.servo.gate", "Button B1 pressed - toggling gate")
        
        # Toggle gate state
        if _gate_open:
            # Gate is open, close it
            _gate_open = False
            set_servo_angle_immediate(0, source="button_B1")
            log("actuator.servo.gate", "Gate: B1 toggle - closing gate")
        else:
            # Gate is closed, open it
            _gate_open = True
            set_servo_angle_immediate(180, source="button_B1")
            log("actuator.servo.gate", "Gate: B1 toggle - opening gate")
    
    # Update last state for next cycle (this tracks the button state over time)
    _last_button_b1_state = current_button_state



def _process_command_queue():
    """Process pending servo commands from the queue.
    
    Executes next command if enough time has passed since last execution.
    Should be called regularly from main loop.
    """
    global _command_queue, _last_command_time_ms
    
    if not _command_queue:
        return
    
    now = ticks_ms()
    time_since_last = ticks_diff(now, _last_command_time_ms) if _last_command_time_ms > 0 else 9999
    
    # Check if we can execute next command
    if time_since_last >= _MIN_COMMAND_INTERVAL_MS:
        # Pop and execute next command
        angle, source = _command_queue.pop(0)
        
        # Check if command is still relevant (not redundant)
        if angle != _angle:
            _execute_servo_command(angle, source)
            log("actuator.servo", "Queue processed: {}° from {} (remaining: {})".format(
                angle, source, len(_command_queue)))
        else:
            log("actuator.servo.debug", "Queue command skipped: already at {}° (remaining: {})".format(
                angle, len(_command_queue)))


def update_gate_automation():
    """Update gate based on presence detection from ESP32-A (called from main loop).
    
    SECURITY ENHANCEMENT: Gate only opens automatically if:
    1. Presence is detected (distance < threshold)
    2. System is in DANGER mode (alarm_level == "danger")
    
    In NORMAL or WARNING modes, presence_detected remains True but servo does not open.
    
    Button B1 override: Can manually toggle gate open/closed regardless of mode.
    """
    global _presence_detected, _gate_open, _presence_lost_time_ms
    
    if _pwm is None:
        return
    
    # Process command queue first (always runs)
    _process_command_queue()
    
    # Skip automation if movement lock is active (prevents interference during commanded movements)
    if not elapsed("servo_movement", _MIN_COMMAND_INTERVAL_MS):
        # Log that automation is blocked (only first time to avoid spam)
        return
    
    # Check for button B1 press to toggle gate (takes precedence)
    _check_button_b1_toggle()
    
    # Read presence state and alarm level from received sensor data
    presence = state.received_sensor_state.get("presence_detected", False)
    alarm_level = state.received_sensor_state.get("alarm_level", "normal")
    
    # SECURITY CHECK: Only allow automatic gate opening in DANGER mode
    # In NORMAL or WARNING modes, presence flag stays True but gate does NOT open
    allow_auto_open = (alarm_level == "danger")
    
    # State change: presence detected in DANGER mode -> open gate
    if presence and allow_auto_open and not _gate_open:
        _gate_open = True
        _presence_lost_time_ms = None
        set_servo_angle_immediate(180, source="automation_danger")  # Open gate immediately
        log("actuator.servo.gate", "Gate: presence detected in DANGER mode, opening...")
    
    # Presence detected but NOT in danger mode -> keep gate closed (do not open)
    elif presence and not allow_auto_open and not _gate_open:
        # Presence is detected but system is in normal/warning mode
        # Log this security action for monitoring
        log("actuator.servo.gate", "Gate: presence detected but in {} mode (not opening)".format(alarm_level))
        pass
    
    # Presence still active in danger mode -> keep gate open
    elif presence and allow_auto_open and _gate_open:
        # Gate already open and presence still detected, nothing to do
        pass
    
    # Presence lost OR not in danger mode -> start countdown to close
    elif (not presence or not allow_auto_open) and _gate_open:
        if _presence_lost_time_ms is None:
            if not presence:
                log("actuator.servo.gate", "Gate: presence lost, countdown to close started")
            else:
                log("actuator.servo.gate", "Gate: system left DANGER mode, countdown to close started")
            _presence_lost_time_ms = ticks_ms()
        else:
            # Check if delay has elapsed
            close_delay_ms = getattr(config, "GATE_CLOSE_DELAY_MS", 10000)
            elapsed_time = ticks_diff(ticks_ms(), _presence_lost_time_ms)
            
            if elapsed_time >= close_delay_ms:
                # Close gate
                log("actuator.servo.gate", "Gate: CLOSING NOW after {:.1f}s delay (presence={}, alarm={}, _gate_open={})".format(
                    close_delay_ms/1000.0, presence, alarm_level, _gate_open))
                _gate_open = False
                _presence_lost_time_ms = None
                set_servo_angle_immediate(0, source="automation_timeout")  # Single command to close
    
    # No presence and gate already closed -> nothing to do
    else:
        pass
    
    _presence_detected = presence
