from machine import ADC, Pin  # type: ignore
import config, state
from timers import elapsed
import time

_adc_x = None
_adc_y = None
_adc_z = None
_sensor_connected = False

def init_accelerometer():
    global _adc_x, _adc_y, _adc_z, _sensor_connected
    try:
        _adc_x = ADC(Pin(config.ACC_X_PIN))
        _adc_y = ADC(Pin(config.ACC_Y_PIN))
        _adc_z = ADC(Pin(config.ACC_Z_PIN))

        for adc in (_adc_x, _adc_y, _adc_z):
            adc.atten(ADC.ATTN_11DB)
        
        from debug import log
        
        # Verifica se il sensore è realmente collegato
        time.sleep_ms(100)  # Attendi stabilizzazione
        
        voltages = []
        for adc in (_adc_x, _adc_y, _adc_z):
            adc_val = adc.read()
            voltage = adc_val * 3.3 / 4095
            voltages.append(voltage)
        
        valid_readings = 0
        for v in voltages:
            if 0.8 < v < 2.5:  # Range realistico per un accelerometro a riposo
                valid_readings += 1
        
        if valid_readings >= 2:  # Almeno 2 assi devono leggere valori validi
            _sensor_connected = True
            log("accelerometer", "Accelerometer initialized and detected")
            return True
        else:
            log("accelerometer", f"Sensor not detected (voltages: {voltages})")
            print("[accelerometer] Sensor not connected - system will continue without accelerometer monitoring")
            _adc_x = None
            _adc_y = None
            _adc_z = None
            _sensor_connected = False
            return False
            
    except Exception as e:
        print(f"[accelerometer] Initialization failed: {e}")
        print("[accelerometer] Sensor disabled - system will continue without accelerometer monitoring")
        _adc_x = None
        _adc_y = None
        _adc_z = None
        _sensor_connected = False
        return False

def read_accelerometer():
    if not _sensor_connected or _adc_x is None or _adc_y is None or _adc_z is None:
        return
    if not elapsed("acc", config.ACC_INTERVAL):
        return

    try:
        for axis, adc in [("x", _adc_x), ("y", _adc_y), ("z", _adc_z)]:
            adc_val = adc.read()
            voltage = adc_val * 3.3 / 4095
            g = (voltage - 1.65) / 0.3
            state.sensor_data["acc"][axis] = round(g, 2)
    except Exception as e:
        from debug import log
        log("accelerometer", f"Read error: {e}")
