from machine import ADC, Pin  # type: ignore
import config, state
from timers import elapsed
from debug import log

_adc = None

def init_co():
    global _adc
    _adc = ADC(Pin(config.CO_PIN))
    _adc.atten(ADC.ATTN_11DB)

def read_co():
    if not elapsed("co", config.CO_INTERVAL):
        return

    value = _adc.read()
    voltage = value * 3.3 / 4095
    state.sensor_data["co"] = round(voltage, 2)
