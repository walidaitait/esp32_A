from machine import SoftI2C, Pin  # type: ignore
from sensors.libs.max30102 import MAX30102, MAX30105_PULSE_AMP_MEDIUM  # type: ignore
import config, state
from timers import elapsed
from debug import log
import time

_i2c = None
_sensor = None
_readings_count = 0
_min_readings_for_valid_bpm = 10  # Numero minimo di letture prima di mostrare BPM

# Beat detection variables
_beat_detector = None

class SimpleBeatDetector:
    """Algoritmo semplice per rilevare battiti cardiaci dal segnale IR"""
    def __init__(self):
        self.ir_buffer = []
        self.buffer_size = 100
        self.threshold_ratio = 0.8  # 80% del range per rilevare picco
        self.last_beat_time = 0
        self.beat_intervals = []
        self.max_intervals = 10
        self.min_peak_distance_ms = 300  # Minimo 300ms tra battiti (200 bpm max)
        
    def add_sample(self, ir_value):
        """Aggiungi un campione IR al buffer"""
        self.ir_buffer.append(ir_value)
        if len(self.ir_buffer) > self.buffer_size:
            self.ir_buffer.pop(0)
    
    def check_for_beat(self, ir_value):
        """Controlla se c'è un battito nel campione corrente"""
        self.add_sample(ir_value)
        
        # Serve almeno 10 campioni per analizzare
        if len(self.ir_buffer) < 10:
            return False
        
        # Calcola media e range
        avg = sum(self.ir_buffer) / len(self.ir_buffer)
        max_val = max(self.ir_buffer)
        min_val = min(self.ir_buffer)
        range_val = max_val - min_val
        
        # Se il range è troppo basso, nessun battito rilevabile
        if range_val < 300:
            return False
        
        # Threshold dinamico basato sul range
        threshold = min_val + (range_val * self.threshold_ratio)
        
        # Rileva picco: valore corrente sopra threshold e maggiore dei vicini
        current_time = time.ticks_ms()
        if len(self.ir_buffer) >= 3:
            if (ir_value > threshold and 
                ir_value > self.ir_buffer[-2] and 
                ir_value > avg):
                
                # Controlla distanza temporale dall'ultimo battito
                time_since_last = time.ticks_diff(current_time, self.last_beat_time)
                if time_since_last > self.min_peak_distance_ms:
                    # Battito rilevato!
                    if self.last_beat_time > 0:
                        self.beat_intervals.append(time_since_last)
                        if len(self.beat_intervals) > self.max_intervals:
                            self.beat_intervals.pop(0)
                    
                    self.last_beat_time = current_time
                    return True
        
        return False
    
    def get_bpm(self):
        """Calcola BPM dalla media degli intervalli tra battiti"""
        if len(self.beat_intervals) < 3:
            return None
        
        # Rimuovi outliers (valori troppo alti o bassi)
        intervals = sorted(self.beat_intervals)
        # Usa solo il 60% centrale dei valori per evitare outliers
        start_idx = len(intervals) // 5
        end_idx = len(intervals) - start_idx
        filtered = intervals[start_idx:end_idx] if len(intervals) > 5 else intervals
        
        if not filtered:
            return None
        
        avg_interval = sum(filtered) / len(filtered)
        bpm = 60000 / avg_interval  # 60000 ms in un minuto
        
        # Filtra valori non realistici
        if 40 <= bpm <= 200:
            return round(bpm, 1)
        return None

def init_heart_rate():
    global _i2c, _sensor, _beat_detector
    try:
        # Inizializza beat detector
        _beat_detector = SimpleBeatDetector()
        # Setup I2C using SoftI2C
        _i2c = SoftI2C(
            sda=Pin(config.HEART_RATE_SDA_PIN),
            scl=Pin(config.HEART_RATE_SCL_PIN),
            freq=400000
        )
        
        # Create sensor instance
        _sensor = MAX30102(i2c=_i2c)
        
        # Check if sensor is detected on I2C bus
        if _sensor.i2c_address not in _i2c.scan():
            print(f"[heart_rate] Sensor not found on I2C bus at address {hex(_sensor.i2c_address)}")
            _sensor = None
            return False
        
        # Check part ID
        if not _sensor.check_part_id():
            print("[heart_rate] Device ID does not correspond to MAX30102 or MAX30105")
            _sensor = None
            return False
        
        # Setup sensor with optimal parameters for heart rate
        _sensor.setup_sensor(
            led_mode=2,  # RED + IR mode (mode 2)
            adc_range=4096,  # ADC range 4096
            sample_rate=100,  # 100 samples/sec
            led_power=MAX30105_PULSE_AMP_MEDIUM,  # Medium LED power
            sample_avg=8,  # Average 8 samples
            pulse_width=411  # Pulse width 411us
        )
        
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
    if _sensor is None or _beat_detector is None:
        return
    if not elapsed("hr", 50):  # Leggi più frequentemente (50ms) per catturare tutti i battiti
        return
    try:
        # Check for new data from sensor
        _sensor.check()
        
        # Check if data is available
        if not _sensor.available():
            # No data available
            if _readings_count == 0:
                state.sensor_data["heart_rate"]["bpm"] = None
                state.sensor_data["heart_rate"]["spo2"] = None
            return
        
        # Get IR and RED readings
        ir_value = _sensor.pop_ir_from_storage()
        red_value = _sensor.pop_red_from_storage()
        
        # Check if finger is present (IR value should be > 10000 for good contact)
        if ir_value < 10000:
            state.sensor_data["heart_rate"]["bpm"] = None
            state.sensor_data["heart_rate"]["spo2"] = None
            if _readings_count == 0:
                log("heart_rate", f"No finger detected (IR: {ir_value})")
            _readings_count = 0
            _beat_detector = SimpleBeatDetector()  # Reset detector
            return
        
        # Finger is present, increment counter
        _readings_count += 1
        
        # Check for beat
        beat_detected = _beat_detector.check_for_beat(ir_value)
        if beat_detected:
            log("heart_rate", f"❤️ Beat detected! IR: {ir_value}")
        
        # Calculate BPM
        bpm = _beat_detector.get_bpm()
        if bpm:
            state.sensor_data["heart_rate"]["bpm"] = bpm
            
            # Calculate SpO2 (approssimativo)
            # Formula semplificata: SpO2 ≈ 110 - 25 * (RED/IR ratio)
            if red_value > 0 and ir_value > 0:
                ratio = (red_value / ir_value)
                spo2 = 110 - (25 * ratio)
                # Limita a range realistico 70-100%
                spo2 = max(70, min(100, spo2))
                state.sensor_data["heart_rate"]["spo2"] = round(spo2, 1)
            else:
                state.sensor_data["heart_rate"]["spo2"] = None
        else:
            # Non ancora abbastanza dati
            if _readings_count < 50:
                state.sensor_data["heart_rate"]["bpm"] = "Warming up..."
                state.sensor_data["heart_rate"]["spo2"] = "Warming up..."
            else:
                state.sensor_data["heart_rate"]["bpm"] = "No signal"
                state.sensor_data["heart_rate"]["spo2"] = "No signal"
        
        # Log periodico
        if _readings_count % 20 == 0:
            log("heart_rate", f"IR: {ir_value}, Red: {red_value}, BPM: {bpm}, Readings: {_readings_count}")
        
    except Exception as e:
        log("heart_rate", f"Read error: {e}")
        state.sensor_data["heart_rate"]["bpm"] = None
        state.sensor_data["heart_rate"]["spo2"] = None
        _readings_count = 0
