from machine import Pin, I2C  # type: ignore
import time
import config, state
from timers import elapsed
from debug import log

_i2c = None
_addr = None
_initialized = False

_backlight = 0x08  # BK=1
_EN = 0x04
_RS = 0x01


def _i2c_write(byte):
    _i2c.writeto(_addr, bytes([byte | _backlight]))


def _pulse(byte):
    _i2c_write(byte | _EN)
    time.sleep_us(1)
    _i2c_write(byte & ~_EN)
    time.sleep_us(50)


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
    time.sleep_ms(50)
    _send_nibble(0x30, 0)
    time.sleep_ms(5)
    _send_nibble(0x30, 0)
    time.sleep_us(150)
    _send_nibble(0x30, 0)
    _send_nibble(0x20, 0)  # 4-bit
    _cmd(0x28)  # 2 linee, 5x8 font
    _cmd(0x08)  # display off
    _cmd(0x01)  # clear
    time.sleep_ms(2)
    _cmd(0x06)  # entry mode
    _cmd(0x0C)  # display on, no cursor


def _set_cursor(line, col):
    addr = 0x80 + (0x40 * line) + col
    _cmd(addr)


def clear():
    if not _initialized:
        return
    _cmd(0x01)
    time.sleep_ms(2)
    state.actuator_state["lcd"]["line1"] = ""
    state.actuator_state["lcd"]["line2"] = ""


def write_line(line, text):
    if not _initialized:
        return
    text = text[:16]
    _set_cursor(line, 0)
    for ch in text:
        _data(ord(ch))


def init_lcd():
    global _i2c, _addr, _initialized
    try:
        _i2c = I2C(
            config.LCD_I2C_ID,
            scl=Pin(config.LCD_SCL_PIN),
            sda=Pin(config.LCD_SDA_PIN),
            freq=400000,
        )
        addrs = _i2c.scan()
        if not addrs:
            log("lcd", "No I2C device found for LCD")
            _initialized = False
            return False
        _addr = addrs[0]
        _init_lcd_hw()
        clear()
        log("lcd", "LCD 16x2 initialized on I2C addr 0x{:02X}".format(_addr))
        _initialized = True
        return True
    except Exception as e:
        print("[lcd] Initialization failed:", e)
        _i2c = None
        _addr = None
        _initialized = False
        return False


_messages = [
    ("ESP32-B ACT TEST", "LED/Servo/LCD/DFP"),
    ("LED sweep", "Servo sweep"),
    ("Buzzer/Audio", "Non-blocking"),
]

_idx = 0


def update_lcd_test():
    """Cambia messaggio ogni LCD_UPDATE_INTERVAL_MS (non bloccante)."""
    global _idx
    if not _initialized or not config.LCD_TEST_ENABLED:
        return

    if not elapsed("lcd_update", config.LCD_UPDATE_INTERVAL_MS):
        return

    title, line2 = _messages[_idx]
    clear()
    write_line(0, title)
    write_line(1, line2)

    state.actuator_state["lcd"]["line1"] = title
    state.actuator_state["lcd"]["line2"] = line2

    _idx = (_idx + 1) % len(_messages)
