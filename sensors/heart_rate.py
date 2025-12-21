from machine import I2C, Pin  # type: ignore
from sensors.libs.max30100 import MAX30100  # type: ignore
import config, state
from timers import elapsed
from debug import log

_i2c = None
_sensor = None

def init_heart_rate():
    global _i2c, _sensor
    _i2c = I2C(0, scl=Pin(config.HEART_RATE_SCL_PIN), sda=Pin(config.HEART_RATE_SDA_PIN))
    _sensor = MAX30100(i2c=_i2c)
    _sensor.enable_spo2()
    log("heart_rate", "Heart rate sensor initialized")

def read_heart_rate():
    if not elapsed("hr", config.HEART_RATE_INTERVAL):
        return
    try:
        _sensor.read_sensor()
        bpm = _sensor.get_heart_rate()
        spo2 = _sensor.get_spo2()
        state.sensor_data["heart_rate"]["bpm"] = round(bpm, 1) if bpm else None
        state.sensor_data["heart_rate"]["spo2"] = round(spo2, 1) if spo2 else None
        log("heart_rate", f"BPM: {bpm}, SpO2: {spo2}")
    except Exception as e:
        log("heart_rate", f"Read error: {e}")
        state.sensor_data["heart_rate"]["bpm"] = None
        state.sensor_data["heart_rate"]["spo2"] = None