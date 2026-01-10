from machine import Pin, UART  # type: ignore
from core import state
from debug.debug import log

_uart = None
_initialized = False


def _send_cmd(cmd, param=0):
    """Send a DFPlayer command (basic protocol)."""
    if _uart is None:
        return

    high = (param >> 8) & 0xFF
    low = param & 0xFF
    version = 0xFF
    length = 0x06
    feedback = 0x00
    total = version + length + cmd + feedback + high + low
    checksum = 0xFFFF - total + 1
    cksH = (checksum >> 8) & 0xFF
    cksL = checksum & 0xFF
    frame = bytes([0x7E, version, length, cmd, feedback, high, low, cksH, cksL, 0xEF])
    _uart.write(frame)


def _set_volume(level):
    level = max(0, min(30, level))
    _send_cmd(0x06, level)


def play_first():
    _send_cmd(0x03, 1)
    state.actuator_state["audio"]["playing"] = True
    state.actuator_state["audio"]["last_cmd"] = "play_first"


def stop():
    _send_cmd(0x16, 0)
    state.actuator_state["audio"]["playing"] = False
    state.actuator_state["audio"]["last_cmd"] = "stop"


def init_audio():
    global _uart, _initialized
    try:
        dfplayer_uart_id = 1
        dfplayer_tx_pin = 27
        dfplayer_rx_pin = 26
        dfplayer_default_volume = 20
        
        _uart = UART(
            dfplayer_uart_id,
            baudrate=9600,
            tx=Pin(dfplayer_tx_pin),
            rx=Pin(dfplayer_rx_pin),
        )
        _set_volume(dfplayer_default_volume)
        log(
            "audio",
            "DFPlayer initialized (UART{}, TX={}, RX={})".format(
                dfplayer_uart_id,
                dfplayer_tx_pin,
                dfplayer_rx_pin,
            ),
        )
        _initialized = True
        return True
    except Exception as e:
        log("actuator.audio", "Initialization failed: {}".format(e))
        _uart = None
        _initialized = False
        return False




def update_audio_test():
    """Placeholder for future audio tests."""
    pass
