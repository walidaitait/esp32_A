"""3-axis accelerometer sensor driver module.

Imported by: core.sensor_loop
Imports: machine.ADC, machine.Pin, config.config, core.state, 
         core.timers, debug.debug

Reads analog 3-axis accelerometer data and converts to g-force values.
- Auto-detects sensor presence (checks for valid voltage ranges)
- Reads X, Y, Z axes via ADC
- Converts voltage to g-force: g = (V - 1.65) / 0.3
- Updates core.state.sensor_data["acc"]["x", "y", "z"]

Note: Board A currently has NO accelerometer hardware wired.
Init will safely fail and subsequent reads are no-ops.
This module exists for future hardware expansion or Board B compatibility.

Typical accelerometer specs:
- Supply: 3.3V
- Output: 0.8V to 2.5V (1.65V = 0g center point)
- Sensitivity: 300mV/g (0.3V/g)
"""

from machine import ADC, Pin  # type: ignore
from config import config
from core import state
from core.timers import elapsed
from debug.debug import log

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
        
        # Check if sensor is actually connected (non-blocking)
        voltages = []
        for adc in (_adc_x, _adc_y, _adc_z):
            adc_val = adc.read()
            voltage = adc_val * 3.3 / 4095
            voltages.append(voltage)
        
        valid_readings = 0
        for v in voltages:
            if 0.8 < v < 2.5:  # Realistic range for resting accelerometer
                valid_readings += 1
        
        if valid_readings >= 2:  # At least 2 axes must read valid values
            _sensor_connected = True
            log("sensor.accelerometer", "init_accelerometer: Accelerometer initialized and detected")
            return True
        else:
            log("sensor.accelerometer", "init_accelerometer: Sensor not detected (voltages: {})".format(voltages))
            _adc_x = None
            _adc_y = None
            _adc_z = None
            _sensor_connected = False
            return False
            
    except Exception as e:
        log("sensor.accelerometer", "init_accelerometer: Initialization failed: {}".format(e))
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
        log("sensor.accelerometer", "read_accelerometer: Read error: {}".format(e))
