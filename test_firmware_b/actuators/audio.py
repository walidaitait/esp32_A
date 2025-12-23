from machine import Pin, UART  # type: ignore
import config, state
from timers import elapsed
from debug import log

_uart = None
_initialized = False


def _send_cmd(cmd, param=0):
    """Invia un comando DFPlayer (protocollo base)."""
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
        _uart = UART(
            config.DFPLAYER_UART_ID,
            baudrate=9600,
            tx=Pin(config.DFPLAYER_TX_PIN),
            rx=Pin(config.DFPLAYER_RX_PIN),
        )
        _set_volume(config.DFPLAYER_DEFAULT_VOLUME)
        log(
            "audio",
            "DFPlayer initialized (UART{}, TX={}, RX={})".format(
                config.DFPLAYER_UART_ID,
                config.DFPLAYER_TX_PIN,
                config.DFPLAYER_RX_PIN,
            ),
        )
        _initialized = True

        if config.AUDIO_AUTOPLAY_ON_START and config.AUDIO_TEST_ENABLED:
            play_first()

        return True
    except Exception as e:
        print("[audio] Initialization failed:", e)
        _uart = None
        _initialized = False
        return False


def update_audio_test():
    """Log periodico dello stato audio (non invasivo)."""
    if not _initialized or not config.AUDIO_TEST_ENABLED:
        return

    if elapsed("audio_status", config.AUDIO_STATUS_PRINT_INTERVAL_MS):
        log(
            "audio",
            "playing={}, last_cmd={}".format(
                state.actuator_state["audio"]["playing"],
                state.actuator_state["audio"]["last_cmd"],
            ),
        )
