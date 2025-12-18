import onewire, ds18x20  # type: ignore
from machine import Pin  # type: ignore
import config, state
from timers import elapsed
from debug import log

_ow = None
_ds = None
_roms = None

def init_temperature():
    global _ow, _ds, _roms
    _ow = onewire.OneWire(Pin(config.TEMP_PIN))
    _ds = ds18x20.DS18X20(_ow)
    _roms = _ds.scan()
    if not _roms:
        log("sensors_temperature", "No DS18B20 sensors found")
    else:
        log("sensors_temperature", f"Found {len(_roms)} DS18B20 sensor(s)")

def read_temperature():
    if not elapsed("temp", config.TEMP_INTERVAL):
        return
    if not _roms:
        return
    _ds.convert_temp()
    # Attendi la conversione (tipicamente 750ms per DS18B20)
    import time
    time.sleep_ms(750)
    temperature = _ds.read_temp(_roms[0])
    state.sensor_data["temperature"] = temperature
    log("sensors_temperature", f"Temperature value: {temperature} °C")
