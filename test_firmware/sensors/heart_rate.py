from machine import I2C, Pin  # type: ignore
from sensors.libs.max30100 import MAX30100  # type: ignore
import config, state
from timers import elapsed
from debug import log

_i2c = None
_sensor = None
_readings_count = 0
_min_readings_for_valid_bpm = 10  # Numero minimo di letture prima di mostrare BPM

def init_heart_rate():
    global _i2c, _sensor
    try:
        _i2c = I2C(0, scl=Pin(config.HEART_RATE_SCL_PIN), sda=Pin(config.HEART_RATE_SDA_PIN), freq=400000)
        _sensor = MAX30100(
            i2c=_i2c,
            mode=0x03,  # SPO2 mode
            sample_rate=100,  # 100 samples/sec - buon bilanciamento
            led_current_red=11.0,  # 11mA - aumentato per migliore rilevamento
            led_current_ir=11.0,   # 11mA
            pulse_width=1600,      # 1600us - massima risoluzione
            max_buffer_len=32      # Buffer per MAX30102
        )
        _sensor.enable_spo2()
        log("heart_rate", "MAX30102 heart rate sensor initialized (place finger gently)")
        print("[heart_rate] For best results: place finger gently without pressing too hard")
        return True
    except Exception as e:
        print(f"[heart_rate] Initialization failed: {e}")
        print("[heart_rate] Sensor disabled - system will continue without heart rate monitoring")
        _sensor = None
        return False

def read_heart_rate():
    global _readings_count
    if _sensor is None:
        return
    if not elapsed("hr", config.HEART_RATE_INTERVAL):
        return
    try:
        # Leggi IR value per verificare se il dito è presente
        _sensor.read_sensor()
        ir_value = _sensor.ir if _sensor.ir else 0
        
        # Se IR value è troppo basso, il dito non è presente o non è posizionato bene
        if ir_value < 50000:  # Soglia tipica per rilevamento dito
            state.sensor_data["heart_rate"]["bpm"] = None
            state.sensor_data["heart_rate"]["spo2"] = None
            _readings_count = 0
            # Log solo ogni 5 secondi per non sovraccaricare
            if _readings_count % 5 == 0:
                log("heart_rate", "No finger detected (IR too low)")
            return
        
        # Dito presente, procedi con la lettura
        _readings_count += 1
        bpm = _sensor.get_heart_rate()
        spo2 = _sensor.get_spo2()
        
        # Mostra BPM solo dopo sufficienti letture per stabilità
        if _readings_count >= _min_readings_for_valid_bpm and bpm:
            # Filtra valori BPM non realistici (normale: 40-200 bpm)
            if 40 <= bpm <= 200:
                state.sensor_data["heart_rate"]["bpm"] = round(bpm, 1)
            else:
                state.sensor_data["heart_rate"]["bpm"] = None
        else:
            state.sensor_data["heart_rate"]["bpm"] = None
        
        # SpO2 è generalmente più stabile
        if spo2 and 70 <= spo2 <= 100:  # Range valido SpO2
            state.sensor_data["heart_rate"]["spo2"] = round(spo2, 1)
        else:
            state.sensor_data["heart_rate"]["spo2"] = None
        
        log("heart_rate", f"BPM: {bpm}, SpO2: {spo2}, IR: {ir_value}, readings: {_readings_count}")
    except Exception as e:
        log("heart_rate", f"Read error: {e}")
        state.sensor_data["heart_rate"]["bpm"] = None
        state.sensor_data["heart_rate"]["spo2"] = None
        _readings_count = 0
