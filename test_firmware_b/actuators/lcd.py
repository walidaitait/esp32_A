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

_page = 0  # per alternare le pagine di stato ogni 2.5s


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


def update_lcd_test():
    """Mostra periodicamente sul display lo stato di tutti gli attuatori.

    Per restare entro i 16 caratteri/linea, il testo viene diviso in
    due "pagine" da ~2.5s ciascuna (metà testo + metà testo), per un
    ciclo completo di circa 5 secondi:

      - Pagina 0: stato sintetico LED + servo
      - Pagina 1: stato sintetico buzzer + audio
    """
    global _page

    if not _initialized or not config.LCD_TEST_ENABLED:
        return

    # Mezzo intervallo: due aggiornamenti per ciclo completo
    half_interval = max(1, config.LCD_UPDATE_INTERVAL_MS // 2)
    if not elapsed("lcd_update", half_interval):
        return

    a = state.actuator_state
    leds_state = a["leds"]
    led_modes = a.get("led_modes", {})
    servo_state = a["servo"]
    buz_state = a["buzzer"]
    audio_state = a["audio"]

    def _led_code(name):
        mode = led_modes.get(name, "off")
        if mode == "on":
            return "1"
        if mode == "blinking":
            return "B"
        return "0"  # off o default

    if _page == 0:
        # Pagina 0: LED + servo
        g = _led_code("green")
        b = _led_code("blue")
        r = _led_code("red")

        # Esempio: "LED G1B0R0" (max ~11 char)
        line1 = "LED G{}B{}R{}".format(g, b, r)

        ang = servo_state.get("angle")
        moving = servo_state.get("moving")
        if ang is None:
            # Servo disabilitato o non inizializzato
            line2 = "Srv:--- {}".format("M" if moving else " ")
        else:
            # Esempio: "Srv:090 M"
            try:
                ang_i = int(ang)
            except Exception:
                ang_i = 0
            line2 = "Srv:{:03d} {}".format(ang_i, "M" if moving else " ")
    else:
        # Pagina 1: buzzer + audio
        buz_on = buz_state.get("active")
        line1 = "Buz:{}".format("ON " if buz_on else "off")

        aud_on = audio_state.get("playing")
        last_cmd = audio_state.get("last_cmd") or "-"
        # Esempio: "Aud:ON  play" (tagliato a 16 char da write_line)
        line2 = "Aud:{} {}".format("ON" if aud_on else "off", last_cmd)

    clear()
    write_line(0, line1)
    write_line(1, line2)

    state.actuator_state["lcd"]["line1"] = line1
    state.actuator_state["lcd"]["line2"] = line2

    # Alterna pagina per il prossimo aggiornamento
    _page = 1 - _page

