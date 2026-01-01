"""Carbon monoxide sensor module.

Reads analog voltage from CO sensor and converts to PPM.
"""
from machine import ADC, Pin  # type: ignore
from config import config
from core import state
from core.timers import elapsed
from debug.debug import log

_adc = None

def init_co():
    global _adc
    try:
        _adc = ADC(Pin(config.CO_PIN))
        _adc.atten(ADC.ATTN_11DB)
        log("co", "init_co: CO sensor initialized")
        return True
    except Exception as e:
        log("co", "init_co: Initialization failed: {}".format(e))
        _adc = None
        return False

def read_co():
    if _adc is None:
        return
    if not elapsed("co", config.CO_INTERVAL):
        return

    try:
        value = _adc.read()
        voltage = value * 3.3 / 4095
        # Convert voltage to PPM
        # Typical formula for CO sensors: PPM = (voltage - 0.1) * 1000 / 3.3
        # Assuming range 0-1000 PPM for 0-3.3V
        ppm = max(0, (voltage - 0.1) * 1000 / 2.2)  # Subtract 0.1V offset
        state.sensor_data["co"] = round(ppm, 2)
    except Exception as e:
        log("co", "read_co: Read error: {}".format(e))
        state.sensor_data["co"] = None
