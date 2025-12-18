from machine import ADC, Pin  # type: ignore
import config, state
from timers import elapsed

_adc_x = None
_adc_y = None
_adc_z = None

def init_accelerometer():
    global _adc_x, _adc_y, _adc_z
    _adc_x = ADC(Pin(config.ACC_X_PIN))
    _adc_y = ADC(Pin(config.ACC_Y_PIN))
    _adc_z = ADC(Pin(config.ACC_Z_PIN))

    for adc in (_adc_x, _adc_y, _adc_z):
        adc.atten(ADC.ATTN_11DB)

def read_accelerometer():
    if not elapsed("acc", config.ACC_INTERVAL):
        return

    for axis, adc in [("x", _adc_x), ("y", _adc_y), ("z", _adc_z)]:
        adc_val = adc.read()
        voltage = adc_val * 3.3 / 4095
        g = (voltage - 1.65) / 0.3
        state.sensor_data["acc"][axis] = round(g, 2)
