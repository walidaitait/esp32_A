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
from time import ticks_ms, ticks_diff  # type: ignore
from config import config
from core import state
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
    log("actuator.servo", "_angle_to_duty angle={} -> pulse_us={} -> duty_10bit={} -> duty_u16={}".format(angle, pulse_us, duty_10bit, duty_16bit))
    return duty_16bit


def _set_angle_immediate(angle):
    """Set servo angle directly (internal use)."""
    global _angle
    if _pwm is None:
        log("actuator.servo", "_set_angle_immediate ignored (PWM not initialized)")
        return
    
    _angle = max(0, min(config.SERVO_MAX_ANGLE, angle))
    try:
        duty_val = _angle_to_duty(_angle)
        _pwm.duty_u16(duty_val)
        log("actuator.servo", "_set_angle_immediate duty_u16({})={}".format(_angle, duty_val))
        state.actuator_state["servo"]["angle"] = _angle
    except Exception as e:
        log("actuator.servo", "Set angle error: {}".format(e))


def set_servo_angle_immediate(angle):
    """Set servo angle instantly."""
    if _pwm is None:
        log("actuator.servo", "set_servo_angle_immediate ignored (PWM not initialized)")
        return

    angle = max(0, min(config.SERVO_MAX_ANGLE, angle))
    _set_angle_immediate(angle)
    log("actuator.servo", "set_servo_angle_immediate angle={}".format(angle))


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
        log("actuator.servo", "init_servo: about to call _set_angle_immediate(0)")
        _set_angle_immediate(_angle)

        log("actuator.servo", "Servo initialized at 0° (immediate movement mode)")
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
    """
    global _gate_open, _last_button_b1_state
    
    # Get current button state from received sensor data (from Board A)
    current_button_state = state.received_sensor_state.get("button_b1", False)
    
    # Detect press event: transition from False to True
    if current_button_state and not _last_button_b1_state:
        log("actuator.servo.gate", "Button B1 pressed - toggling gate")
        
        # Toggle gate state
        if _gate_open:
            # Gate is open, close it
            _gate_open = False
            set_servo_angle_immediate(0)
            log("actuator.servo.gate", "Gate: B1 toggle - closing gate")
        else:
            # Gate is closed, open it
            _gate_open = True
            set_servo_angle_immediate(180)
            log("actuator.servo.gate", "Gate: B1 toggle - opening gate")
    
    # Update last state for next cycle
    _last_button_b1_state = current_button_state



def update_gate_automation():
    """Update gate based on presence detection from ESP32-A (called from main loop).
    
    SECURITY ENHANCEMENT: Gate only opens automatically if:
    1. Presence is detected (distance < threshold)
    2. System is in DANGER mode (alarm_level == "danger")
    
    In NORMAL or WARNING modes, presence_detected remains True but servo does not open.
    
    Button B1 override: Can manually toggle gate open/closed regardless of mode.
    """
    global _presence_detected, _gate_open, _presence_lost_time_ms, _target_angle
    
    if _pwm is None:
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
        set_servo_angle_immediate(180)  # Open gate immediately
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
            elapsed = ticks_diff(ticks_ms(), _presence_lost_time_ms)
            
            if elapsed >= close_delay_ms:
                # Close gate
                _gate_open = False
                _presence_lost_time_ms = None
                set_servo_angle_immediate(0)  # Close gate
                log("actuator.servo.gate", "Gate: closing after delay ({} ms)".format(close_delay_ms))
    
    # No presence and gate already closed -> nothing to do
    else:
        pass
    
    _presence_detected = presence
