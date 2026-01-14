from machine import Pin, PWM  # type: ignore
from time import ticks_ms, ticks_diff  # type: ignore
from core import state
from debug.debug import log

_pwm = None
_initialized = False

# ============================================================================
# SOUND DEFINITIONS - Add new sounds here in the future
# Format: (duration_ms, is_tone_on, frequency_hz)
# ============================================================================
_sounds = {
    "warning": [
        (200, True, 1200),      # beep 1
        (100, False, 0),        # pause between beeps
        (200, True, 1200),      # beep 2
        (2000, False, 0),       # long pause before repeat
    ],
    "danger": [
        (500, True, 1800),      # beep 1 (long)
        (200, False, 0),        # pause between beeps
        (500, True, 1800),      # beep 2 (long)
        (1000, False, 0),       # pause before repeat
    ],
}

# Sound playback state
_current_sound = None           # Name of currently playing sound (or None)
_sound_start_ms = 0             # When current sound phase started
_sound_phase = 0                # Which phase we're in
_tone_active = False            # Is tone currently playing


def set_tone(freq):
    """Set a continuous frequency (0 = silence) non-blocking mode.

    Used by both buzzer internal test and integrated servo test.
    """
    global _pwm

    if not _initialized or _pwm is None:
        return

    try:
        if freq > 0:
            try:
                _pwm.freq(freq)
            except Exception as e:
                log("actuator.buzzer", "freq set error: {}".format(e))
            _pwm.duty(512)
            state.actuator_state["buzzer"]["active"] = True
        else:
            _pwm.duty(0)
            state.actuator_state["buzzer"]["active"] = False
    except Exception as e:
        log("actuator.buzzer", "PWM error: {}".format(e))


def init_buzzer():
    global _pwm, _initialized
    try:
        buzzer_pin = 25  # GPIO25
        pin = Pin(buzzer_pin, Pin.OUT)
        _pwm = PWM(pin, freq=1000)
        _pwm.duty(0)

        state.actuator_state["buzzer"]["active"] = False
        _initialized = True

        log("actuator.buzzer", "Passive buzzer initialized on GPIO{}".format(buzzer_pin))
        return True
    except Exception as e:
        log("actuator.buzzer", "Initialization failed: {}".format(e))
        _pwm = None
        _initialized = False
        return False


def play_sound(sound_name):
    """Start playing a sound from the sounds dictionary.
    
    Args:
        sound_name: Key in _sounds dict (e.g., "warning", "danger")
    
    Returns:
        True if sound started, False if not found
    """
    global _current_sound, _sound_start_ms, _sound_phase, _tone_active
    
    if not _initialized:
        return False
    
    if sound_name not in _sounds:
        log("actuator.buzzer", "play_sound: Sound '{}' not found".format(sound_name))
        return False
    
    if _current_sound != sound_name:
        _current_sound = sound_name
        _sound_phase = 0
        _sound_start_ms = ticks_ms()
        _tone_active = False
        log("actuator.buzzer", "play_sound: Starting '{}'".format(sound_name))
    
    return True


def stop_sound():
    """Stop current sound playback immediately."""
    global _current_sound, _tone_active
    
    if _current_sound is not None:
        log("actuator.buzzer", "stop_sound: Stopping '{}'".format(_current_sound))
        _current_sound = None
        _tone_active = False
        set_tone(0)
    else:
        _tone_active = False
        set_tone(0)


def update():
    """Update sound playback state (call every loop cycle).
    
    Handles phase transitions and tone playback without blocking.
    """
    global _current_sound, _sound_start_ms, _sound_phase, _tone_active
    
    if not _initialized or _current_sound is None:
        # No sound playing, ensure buzzer is off
        if _tone_active:
            set_tone(0)
            _tone_active = False
        return
    
    sound_pattern = _sounds[_current_sound]
    now = ticks_ms()
    
    # Get current phase info
    duration_ms, should_beep, freq = sound_pattern[_sound_phase]
    
    # Check if we need to advance to next phase
    elapsed_in_phase = ticks_diff(now, _sound_start_ms)
    
    if elapsed_in_phase >= duration_ms:
        # Move to next phase (loop back to start)
        _sound_phase = (_sound_phase + 1) % len(sound_pattern)
        _sound_start_ms = now
        
        # Get new phase info
        duration_ms, should_beep, freq = sound_pattern[_sound_phase]
    
    # Apply tone for current phase
    if should_beep and freq > 0:
        if not _tone_active:
            set_tone(freq)
            _tone_active = True
    else:
        if _tone_active:
            set_tone(0)
            _tone_active = False


def update_alarm_feedback(level):
    """Drive buzzer based on alarm level.
    
    WARNING: plays "warning" sound
    DANGER: plays "danger" sound
    NORMAL: stops all sounds
    """
    if not _initialized:
        return
    
    if level == "normal":
        stop_sound()
        state.actuator_state["buzzer"]["alarm_muted"] = False
    elif level == "warning":
        if state.actuator_state["buzzer"].get("alarm_muted"):
            stop_sound()
            log("actuator.buzzer", "update_alarm_feedback: WARNING sound muted by user")
            return
        play_sound("warning")
    elif level == "danger":
        if state.actuator_state["buzzer"].get("alarm_muted"):
            stop_sound()
            log("actuator.buzzer", "update_alarm_feedback: DANGER sound muted by user")
            return
        play_sound("danger")


def update_buzzer_test():
    """Placeholder for future buzzer tests."""
    pass