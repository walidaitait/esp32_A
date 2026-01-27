"""DS18B20 temperature sensor driver module.

Imported by: core.sensor_loop
Imports: onewire, ds18x20 (MicroPython), machine.Pin, time, config.config, 
         core.state, core.timers, debug.debug

Reads temperature from DS18B20 OneWire digital temperature sensor.
- Non-blocking: Uses two-step read (trigger conversion, wait 750ms, read value)
- Auto-detects all DS18B20 devices on the OneWire bus
- Updates core.state.sensor_data["temperature"] with Celsius values
- Handles conversion timing to avoid blocking the main loop

Note: Conversion takes 750ms. First call triggers conversion, second call
(after 750ms) reads the result. This prevents blocking during conversion.
"""

import onewire, ds18x20  # type: ignore
from machine import Pin  # type: ignore
from time import ticks_ms, ticks_diff  # type: ignore
from config import config
from core import state
from core.timers import elapsed
from debug.debug import log

_ow = None
_ds = None
_roms = None
_conversion_start_time = 0
_conversion_pending = False

def init_temperature():
    global _ow, _ds, _roms
    try:
        _ow = onewire.OneWire(Pin(config.TEMP_PIN))
        _ds = ds18x20.DS18X20(_ow)
        _roms = _ds.scan()
        if not _roms:
            log("sensor.temperature", "init_temperature: No DS18B20 sensors found")
            return False
        else:
            log("sensor.temperature", "init_temperature: Found {} DS18B20 sensor(s)".format(len(_roms)))
            return True
    except Exception as e:
        log("sensor.temperature", "init_temperature: Initialization failed: {}".format(e))
        _ow = None
        _ds = None
        _roms = None
        return False

def read_temperature():
    global _conversion_start_time, _conversion_pending
    if _ds is None or not _roms:
        return
    if not elapsed("temp", config.TEMP_INTERVAL):
        return
    
    now = ticks_ms()
    
    try:
        if not _conversion_pending:
            # Start conversion
            _ds.convert_temp()
            _conversion_start_time = now
            _conversion_pending = True
            return
        
        # Check if conversion is done (750ms)
        if ticks_diff(now, _conversion_start_time) >= 750:
            temperature = _ds.read_temp(_roms[0])
            state.sensor_data["temperature"] = temperature
            _conversion_pending = False
    except Exception as e:
        log("sensor.temperature", "read_temperature: Read error: {}".format(e))
        _conversion_pending = False
