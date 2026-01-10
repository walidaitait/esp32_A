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

_backlight = 0x08  # BK=1
_EN = 0x04
_RS = 0x01


def _i2c_write(byte):
    if _i2c is None:
        return
    _i2c.writeto(_addr, bytes([byte | _backlight]))


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
            log("lcd", "No I2C device found for LCD")
            _initialized = False
            return False
        _addr = addrs[0]
        _init_lcd_hw()
        # Mark initialized before issuing clear so guard does not skip it
        _initialized = True
        clear()
        log("lcd", "LCD 16x2 initialized on I2C addr 0x{:02X}".format(_addr))
        return True
    except Exception as e:
        log("lcd", "Initialization failed: {}".format(e))
        _i2c = None
        _addr = None
        _initialized = False
        return False




def update_lcd_test():
    """Update LCD: handle pending operations and restore default if needed."""
    if not _initialized:
        return
    # Check if clear command has completed
    _check_clear_complete()
    # If not displaying custom content and no clear pending, restore default
    if not _displaying_custom and not _clear_pending:
        restore_default()

