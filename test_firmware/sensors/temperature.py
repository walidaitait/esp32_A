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
    try:
        _ow = onewire.OneWire(Pin(config.TEMP_PIN))
        _ds = ds18x20.DS18X20(_ow)
        _roms = _ds.scan()
        if not _roms:
            log("temperature", "No DS18B20 sensors found")
            return False
        else:
            log("temperature", f"Found {len(_roms)} DS18B20 sensor(s)")
            return True
    except Exception as e:
        print(f"[temperature] Initialization failed: {e}")
        print("[temperature] Sensor disabled - system will continue without temperature monitoring")
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
    
    import time
    now = time.ticks_ms()
    
    try:
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
            # log("temperature", f"Temperature value: {temperature} °C")
            _conversion_pending = False
    except Exception as e:
        log("temperature", f"Read error: {e}")
        _conversion_pending = False
