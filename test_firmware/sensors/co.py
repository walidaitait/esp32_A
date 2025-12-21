from machine import ADC, Pin  # type: ignore
import config, state
from timers import elapsed
from debug import log

_adc = None

def init_co():
    global _adc
    try:
        _adc = ADC(Pin(config.CO_PIN))
        _adc.atten(ADC.ATTN_11DB)
        log("co", "CO sensor initialized")
        return True
    except Exception as e:
        print(f"[co] Initialization failed: {e}")
        print("[co] Sensor disabled - system will continue without CO monitoring")
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
        # Converti voltage in PPM
        # Formula tipica per sensori CO: PPM = (voltage - 0.1) * 1000 / 3.3
        # Assumendo range 0-1000 PPM per 0-3.3V
        ppm = max(0, (voltage - 0.1) * 1000 / 2.2)  # sottrai offset di 0.1V
        state.sensor_data["co"] = round(ppm, 2)
    except Exception as e:
        log("co", f"Read error: {e}")
        state.sensor_data["co"] = None
