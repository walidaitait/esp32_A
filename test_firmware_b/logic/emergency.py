"""Emergency SOS system for ESP32-B.

Monitors button press patterns to detect emergency situations:
- Hold button for 5 seconds → activate SOS call
- Press button 5 times within 2 seconds → activate SOS call

Once in SOS state, display emergency message and lock actuators.
Exit SOS state by pressing button again (single click).
"""
from time import ticks_ms, ticks_diff  # type: ignore
from core import state
from debug.debug import log

# SOS detection thresholds
LONG_PRESS_DURATION_MS = 5000      # 5 seconds hold
RAPID_CLICK_COUNT = 5               # 5 clicks (press+release)
RAPID_CLICK_WINDOW_MS = 2000        # within 2 seconds

# SOS state tracking
_sos_active = False
_button_press_start = None          # When button was pressed (for long press detection)
_click_count = 0                    # Count of clicks (press+release cycles)
_last_click_time = None             # Timestamp of last click
_last_button_state = False          # Previous button state for edge detection
_sos_button_pressed = False         # Track if button was pressed during SOS (waiting for release)
_temp_muted = False                 # Temporary mute flag (set on first click, cleared if more clicks arrive)


def update():
    """Update SOS detection logic.
    
    Call this regularly from main loop to detect SOS patterns.
    Returns dict with detected events for actuator loop to handle.
    """
    global _sos_active, _button_press_start, _click_count, _last_click_time, _last_button_state, _sos_button_pressed, _temp_muted
    
    current_button = state.actuator_state.get("button", False)
    now = ticks_ms()
    
    result = {
        "sos_activated": False,      # True if SOS just activated
        "sos_deactivated": False,    # True if SOS just deactivated
        "single_click": False,       # True if single click detected (context-dependent action)
        "temp_muted": False,         # True if temporary muting requested (immediate)
        "unmute": False,             # True if muting should be cleared (more clicks arriving)
    }
    
    # === SOS ACTIVE STATE ===
    # If SOS is already active, only listen for full click (press+release) to exit
    if _sos_active:
        # Detect button press (rising edge: False → True)
        # current_button = True means pressed, False means NOT pressed
        if current_button and not _last_button_state:
            _sos_button_pressed = True
            log("emergency", "SOS mode: Button pressed (waiting for release)")
        
        # Detect button release (falling edge: True → False)
        elif not current_button and _last_button_state:
            if _sos_button_pressed:
                # Complete click detected (press + release) = close SOS call
                _sos_active = False
                _sos_button_pressed = False
                result["sos_deactivated"] = True
                result["single_click"] = True  # Signal it was a single click action
                log("emergency", "SOS call ended by complete button click (press+release)")
        
        _last_button_state = current_button
        state.actuator_state["button"] = current_button  # Keep state updated
        return result
    
    # === SOS DETECTION STATE ===
    # Detect rising edge (button pressed: False → True)
    # current_button = True means pressed, False means NOT pressed
    if current_button and not _last_button_state:
        _button_press_start = now
        log("emergency", "Button pressed at {}".format(now))
    
    # Detect falling edge (button released: True → False) = completed click
    elif not current_button and _last_button_state:
        if _button_press_start is not None:
            press_duration = ticks_diff(now, _button_press_start)
            log("emergency", "Button released, duration: {} ms".format(press_duration))
            
            # Increment click counter
            if _last_click_time is None or ticks_diff(now, _last_click_time) > RAPID_CLICK_WINDOW_MS:
                # Start new click sequence (window expired or first click)
                _click_count = 1
                _last_click_time = now
                log("emergency", "Click count reset: 1")
                
                # IMMEDIATE MUTING on first click (don't wait for window to expire)
                global _temp_muted
                _temp_muted = True
                result["temp_muted"] = True
                log("emergency", "First click detected - TEMP MUTE buzzer immediately")
            else:
                # Within click window, increment count
                _click_count += 1
                _last_click_time = now
                log("emergency", "Click count: {}".format(_click_count))
                
                # If this is the 2nd+ click, UNMUTE (user is trying for SOS)
                if _click_count >= 2 and _temp_muted:
                    _temp_muted = False
                    result["unmute"] = True
                    log("emergency", "Additional click detected - UNMUTE buzzer (SOS sequence)")
                
                # Check if rapid click threshold reached (5 clicks)
                if _click_count >= RAPID_CLICK_COUNT:
                    _sos_active = True
                    result["sos_activated"] = True
                    _click_count = 0
                    _last_click_time = None
                    _temp_muted = False  # Clear temp mute on SOS activation
                    log("emergency", "SOS ACTIVATED (5 rapid clicks)")
            
            _button_press_start = None
    
    # Check for long press (while button is still held)
    # NOTE: small timing jitter on ticks_ms can cause borderline presses to land just under/over
    # the 5s threshold. No mitigation added here (Problem 10 note).
    # current_button = True means button is pressed (pin LOW)
    elif current_button and _button_press_start is not None:
        press_duration = ticks_diff(now, _button_press_start)
        
        # Check if long press threshold reached (5 seconds)
        if press_duration >= LONG_PRESS_DURATION_MS:
            _sos_active = True
            result["sos_activated"] = True
            _button_press_start = None  # Reset to avoid re-triggering
            _click_count = 0
            _last_click_time = None
            log("emergency", "SOS ACTIVATED (long press 5s)")
    
    # Check if we have a single completed click (not part of rapid sequence)
    if _last_click_time is not None and ticks_diff(now, _last_click_time) > RAPID_CLICK_WINDOW_MS:
        if _click_count == 1:
            # Single click detected (not rapid sequence)
            result["single_click"] = True
            log("emergency", "Single click detected (context-dependent action)")
            _temp_muted = False  # Clear temp flag after finalizing single-click action
        
        # Reset click counter (window expired)
        if _click_count > 0 and _click_count < RAPID_CLICK_COUNT:
            log("emergency", "Click window expired, count was {} (not enough for SOS)".format(_click_count))
        _click_count = 0
        _last_click_time = None
        if _temp_muted and _click_count == 0:
            _temp_muted = False
    
    _last_button_state = current_button
    return result


def is_sos_active():
    """Check if SOS is currently active."""
    return _sos_active


def force_deactivate_sos():
    """Force deactivate SOS (for emergency override)."""
    global _sos_active
    if _sos_active:
        _sos_active = False
        log("emergency", "SOS force deactivated")
        return True
    return False
