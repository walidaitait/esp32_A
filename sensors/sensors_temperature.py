from machine import ADC, Pin
import config, state
from timers import elapsed
from debug import log

_adc = ADC(Pin(config.TEMP_PIN))
_adc.atten(ADC.ATTN_11DB)

def read_temperature():
    if not elapsed("temp", config.TEMP_INTERVAL):
        return
    raw = _adc.read()
    voltage = raw * 3.3 / 4095

    # Conversione generica (modificabile)
    temperature = voltage * 100  
    state.sensor_data["temperature"] = temperature
    log("sensors_temperature", f"Temperature value: {temperature}")
