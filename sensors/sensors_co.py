from machine import ADC, Pin
import config, state
from timers import elapsed
from debug import log

_adc = ADC(Pin(config.CO_PIN))
_adc.atten(ADC.ATTN_11DB)

def read_co():
    if not elapsed("co", config.CO_INTERVAL):
        return

    value = _adc.read()
    state.sensor_data["co"] = value
