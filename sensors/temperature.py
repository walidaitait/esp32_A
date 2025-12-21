import onewire, ds18x20  # type: ignore
from machine import Pin  # type: ignore
import config, state
from timers import elapsed
from debug import log

_ow = None
_ds = None
_roms = None
_conversion_start_time = 0
_conversion_pending = False

def init_temperature():
    global _ow, _ds, _roms
    _ow = onewire.OneWire(Pin(config.TEMP_PIN))
    _ds = ds18x20.DS18X20(_ow)
    _roms = _ds.scan()
    if not _roms:
        log("temperature", "No DS18B20 sensors found")
    else:
        log("temperature", f"Found {len(_roms)} DS18B20 sensor(s)")

def read_temperature():
    global _conversion_start_time, _conversion_pending
    if not elapsed("temp", config.TEMP_INTERVAL):
        return
    if not _roms:
        return
    
    import time
    now = time.ticks_ms()
    
    if not _conversion_pending:
        # Start conversion
        _ds.convert_temp()
        _conversion_start_time = now
        _conversion_pending = True
        return
    
    # Check if conversion is done (750ms)
    if time.ticks_diff(now, _conversion_start_time) >= 750:
        temperature = _ds.read_temp(_roms[0])
        state.sensor_data["temperature"] = temperature
        log("temperature", f"Temperature value: {temperature} °C")
        _conversion_pending = False
    # Else, wait for next call
