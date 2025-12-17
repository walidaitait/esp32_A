from machine import ADC, Pin
import config, state
from timers import elapsed

_adc_x = ADC(Pin(config.ACC_X_PIN))
_adc_y = ADC(Pin(config.ACC_Y_PIN))
_adc_z = ADC(Pin(config.ACC_Z_PIN))

for adc in (_adc_x, _adc_y, _adc_z):
    adc.atten(ADC.ATTN_11DB)

def read_accelerometer():
    if not elapsed("acc", config.ACC_INTERVAL):
        return

    state.sensor_data["acc"]["x"] = _adc_x.read()
    state.sensor_data["acc"]["y"] = _adc_y.read()
    state.sensor_data["acc"]["z"] = _adc_z.read()
