"""LCD 1602A display driver with I2C backpack for ESP32-B.

Imported by: core.actuator_loop
Imports: machine (Pin, I2C), time, core.state, core.timers, debug.debug

Controls 16x2 character LCD display via I2C PCF8574 backpack.
Displays system status, alarm levels, and sensor readings.

Default idle text:
- Line 1: "System Ready"
- Line 2: "Standby..."

In alarm states, displays relevant sensor data and alarm level.

Hardware: LCD 1602A + I2C backpack @ address 0x27, SDA=GPIO21, SCL=GPIO22
Protocol: I2C 4-bit mode with EN/RS control via PCF8574 expander
"""
from machine import Pin, I2C  # type: ignore
from time import sleep_ms, sleep_us, ticks_ms, ticks_diff  # type: ignore
from core import state, timers
from debug.debug import log

# Default display text for idle state
DEFAULT_LINE1 = "System Ready"
DEFAULT_LINE2 = "Standby..."

_i2c = None
_addr = None
_initialized = False
_displaying_custom = False  # Track if custom content is being displayed
_clear_pending = False  # Track if clear command is waiting for hardware
_clear_start = 0  # Timestamp when clear was issued

_backlight_enabled = True  # Backlight state
_backlight = 0x08  # BK=1
_EN = 0x04
_RS = 0x01


def _i2c_write(byte):
    if _i2c is None:
        return
    backlight_bit = _backlight if _backlight_enabled else 0x00
    _i2c.writeto(_addr, bytes([byte | backlight_bit]))


def _pulse(byte):
    _i2c_write(byte | _EN)
    sleep_us(1)
    _i2c_write(byte & ~_EN)
    sleep_us(50)


def _send_nibble(nibble, rs):
    b = (nibble & 0xF0)
    if rs:
        b |= _RS
    _pulse(b)


def _send_byte(value, rs):
    _send_nibble(value & 0xF0, rs)
    _send_nibble((value << 4) & 0xF0, rs)


def _cmd(cmd):
    _send_byte(cmd, rs=0)


def _data(d):
    _send_byte(d, rs=1)


def _init_lcd_hw():
    sleep_ms(50)
    _send_nibble(0x30, 0)
    sleep_ms(5)
    _send_nibble(0x30, 0)
    sleep_us(150)
    _send_nibble(0x30, 0)
    _send_nibble(0x20, 0)  # 4-bit
    _cmd(0x28)  # 2 lines, 5x8 font
    _cmd(0x08)  # display off
    _cmd(0x01)  # clear
    sleep_ms(2)
    _cmd(0x06)  # entry mode
    _cmd(0x0C)  # display on, no cursor


def _set_cursor(line, col):
    addr = 0x80 + (0x40 * line) + col
    _cmd(addr)


def set_backlight(enabled):
    """Turn LCD backlight on or off.
    
    Args:
        enabled: True to turn on, False to turn off
    """
    global _backlight_enabled
    if not _initialized:
        return
    _backlight_enabled = enabled
    # Send a dummy write to update backlight immediately
    _i2c_write(0x00)
    log("actuator.lcd", "Backlight {}".format("ON" if enabled else "OFF"))


def clear():
    """Clear LCD and mark for deferred default text display (non-blocking)."""
    global _displaying_custom, _clear_pending, _clear_start
    _cmd(0x01)
    _clear_pending = True
    _clear_start = ticks_ms()
    _displaying_custom = False


def write_line(line, text):
    if not _initialized:
        return
    text = text[:16]
    # Pad with spaces to clear the entire 16-character line
    text = text + ' ' * (16 - len(text))
    _set_cursor(line, 0)
    for ch in text:
        _data(ord(ch))


def display_custom(line1, line2):
    """Display custom text on LCD and mark as custom content."""
    global _displaying_custom
    if not _initialized:
        return
    write_line(0, line1)
    write_line(1, line2)
    state.actuator_state["lcd"]["line1"] = line1
    state.actuator_state["lcd"]["line2"] = line2
    _displaying_custom = True


def restore_default():
    """Restore default text without full clear (no sleep)."""
    global _displaying_custom
    if not _initialized:
        return
    write_line(0, DEFAULT_LINE1)
    write_line(1, DEFAULT_LINE2)
    state.actuator_state["lcd"]["line1"] = DEFAULT_LINE1
    state.actuator_state["lcd"]["line2"] = DEFAULT_LINE2
    _displaying_custom = False


def _check_clear_complete():
    """Check if clear command has completed (2ms delay for LCD hardware)."""
    global _clear_pending
    if _clear_pending:
        if ticks_diff(ticks_ms(), _clear_start) >= 2:
            # Clear completed, display default text
            write_line(0, DEFAULT_LINE1)
            write_line(1, DEFAULT_LINE2)
            state.actuator_state["lcd"]["line1"] = DEFAULT_LINE1
            state.actuator_state["lcd"]["line2"] = DEFAULT_LINE2
            _clear_pending = False


def init_lcd():
    global _i2c, _addr, _initialized
    try:
        lcd_i2c_id = 0
        lcd_scl_pin = 22
        lcd_sda_pin = 21
        
        _i2c = I2C(
            lcd_i2c_id,
            scl=Pin(lcd_scl_pin),
            sda=Pin(lcd_sda_pin),
            freq=400000,
        )
        addrs = _i2c.scan()
        if not addrs:
            log("actuator.lcd", "No I2C device found for LCD")
            _initialized = False
            return False
        _addr = addrs[0]
        _init_lcd_hw()
        # Mark initialized before issuing clear so guard does not skip it
        _initialized = True
        clear()
        log("actuator.lcd", "LCD 16x2 initialized on I2C addr 0x{:02X}".format(_addr))
        return True
    except Exception as e:
        log("actuator.lcd", "Initialization failed: {}".format(e))
        _i2c = None
        _addr = None
        _initialized = False
        return False




def update_lcd_test():
    """Update LCD: handle pending operations and restore default if needed.
    
    Does NOT restore default if there's an active user lock (custom content from commands).
    """
    if not _initialized:
        return
    
    # Check if clear command has completed
    _check_clear_complete()
    
    # Import timers here to check if user has locked the LCD
    from core import timers
    lcd_locked = timers.user_override_active("lcd_update")
    
    # Only restore default if:
    # - Not currently displaying custom content AND
    # - No clear pending AND  
    # - User hasn't locked LCD via command
    if not _displaying_custom and not _clear_pending and not lcd_locked:
        restore_default()


def update_alarm_display(level, source):
    """Display alarm info. Normal -> default; warning/danger -> show messages.
    
    Note: Only called when user_override_active("lcd_update") is False,
    so it respects custom LCD content set via commands.
    """
    if not _initialized:
        return
    if level == "normal":
        # Only restore default if we were showing alarm
        if _displaying_custom:
            log("actuator.lcd", "update_alarm_display: Clearing alarm display (normal)")
            restore_default()
        return

    line1 = "Warning" if level == "warning" else "Danger"
    line2 = source.upper() if source else "ALARM"
    log("actuator.lcd", "update_alarm_display: LCD '{}' / '{}' ({})".format(line1, line2, level))
    display_custom(line1[:16], line2[:16])

