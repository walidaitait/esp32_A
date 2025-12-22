from machine import SoftI2C, Pin  # type: ignore
from sensors.libs.max30102 import MAX30102, MAX30105_PULSE_AMP_MEDIUM  # type: ignore
import config, state
from timers import elapsed
from debug import log
import time

_i2c = None
_sensor = None
_readings_count = 0

# Buffers per analisi del segnale
_ir_buffer = []
_red_buffer = []
_buffer_size = 100  # 100 campioni = 1 secondo a 100Hz

# Variabili per calibrazione automatica
_baseline_ir = 0
_baseline_red = 0
_finger_threshold = 5000  # Soglia calibrata automaticamente

# Variabili per calcolo BPM
_last_peak_time = 0
_last_peak_value = 0
_bpm_buffer = []
_bpm_buffer_size = 2  # Ridotto a 2 per output più rapido
_estimated_bpm = None  # Stima BPM prima del secondo picco

# Variabili per calcolo SpO2
_spo2_buffer = []
_spo2_buffer_size = 10

def init_heart_rate():
    global _i2c, _sensor
    try:
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
        
        # Setup sensor - configurazione ottimale per leggere RED e IR
        _sensor.setup_sensor(
            led_mode=2,  # RED + IR mode (mode 2)
            adc_range=16384,  # ADC range massimo per maggiore risoluzione
            sample_rate=100,  # 100 samples/sec
            led_power=MAX30105_PULSE_AMP_MEDIUM,  # Medium LED power  
            sample_avg=8,  # Average 8 samples
            pulse_width=411  # Pulse width 411us - massima sensibilità
        )
        
        log("heart_rate", "MAX30102 initialized - Reading RED and IR values")
        print("[heart_rate] Sensor ready. Place finger gently on sensor.")
        return True
    except Exception as e:
        print(f"[heart_rate] Initialization failed: {e}")
        print("[heart_rate] Sensor disabled")
        _sensor = None
        return False

def _calibrate_baseline():
    """Calibra il baseline quando non c'è il dito"""
    global _baseline_ir, _baseline_red, _finger_threshold
    
    if len(_ir_buffer) < 20:
        return False
    
    # Calcola media degli ultimi 20 campioni
    recent_ir = _ir_buffer[-20:]
    recent_red = _red_buffer[-20:]
    
    avg_ir = sum(recent_ir) / len(recent_ir)
    avg_red = sum(recent_red) / len(recent_red)
    
    # Se i valori sono bassi (<3000), è baseline
    if avg_ir < 3000:
        _baseline_ir = avg_ir
        _baseline_red = avg_red
        _finger_threshold = _baseline_ir + 5000  # Soglia = baseline + 5000
        return True
    
    return False

def _detect_finger(ir_value):
    """Rileva se il dito è presente"""
    global _finger_threshold
    
    # Se non abbiamo ancora calibrato, usa soglia di default
    if _baseline_ir == 0:
        # Valori bassi = no finger, valori alti = finger
        return ir_value > 5000
    
    # Usa soglia calibrata
    return ir_value > _finger_threshold

def _calculate_dc_component(buffer):
    """Calcola componente DC (media) di un buffer"""
    if len(buffer) < 10:
        return 0
    return sum(buffer[-50:]) / min(50, len(buffer))

def _calculate_ac_component(buffer, dc_value):
    """Calcola componente AC (variazione) di un buffer"""
    if len(buffer) < 10:
        return 0
    
    # AC = deviazione standard degli ultimi valori
    recent = buffer[-50:]
    variance = sum((x - dc_value) ** 2 for x in recent) / len(recent)
    return variance ** 0.5

def _detect_peak(ir_value):
    """Rileva picchi per calcolare BPM"""
    global _last_peak_time, _last_peak_value, _bpm_buffer, _estimated_bpm
    
    if len(_ir_buffer) < 3:
        return None
    
    # Usa ultimi 3 valori per rilevare massimo locale in tempo reale
    # [n-2, n-1, n] -> n-1 è picco se n-1 > n-2 e n-1 > n
    if len(_ir_buffer) >= 3:
        prev_prev = _ir_buffer[-3]
        prev = _ir_buffer[-2]
        current = _ir_buffer[-1]
        
        # Il valore precedente è un picco se maggiore di entrambi i vicini
        is_peak = prev > prev_prev and prev > current
        
        # Soglia ulteriormente ridotta per massima sensibilità
        min_prominence = 30  # Ridotto a 30 per rilevare più picchi
        is_prominent = (prev - prev_prev > min_prominence) and (prev - current > min_prominence)
        
        if is_peak and is_prominent:
            current_time = time.ticks_ms()
            
            # Se abbiamo un picco precedente, calcoliamo BPM
            if _last_peak_time > 0:
                time_diff = time.ticks_diff(current_time, _last_peak_time)
                
                # Range molto ampio per BPM (25-240)
                if 250 < time_diff < 2400:  # 250ms = 240BPM, 2400ms = 25BPM
                    bpm = 60000 / time_diff
                    _bpm_buffer.append(bpm)
                    
                    # Mantieni buffer limitato
                    if len(_bpm_buffer) > _bpm_buffer_size:
                        _bpm_buffer.pop(0)
                    
                    _last_peak_time = current_time
                    _last_peak_value = prev
                    
                    # log("heart_rate", f"Peak detected! BPM: {bpm:.1f}, time_diff: {time_diff}ms")
                    return bpm
                else:
                    # Accetta comunque il picco anche fuori range
                    if time_diff > 2400:
                        bpm = 30  # Stima minima
                    else:
                        bpm = 240  # Stima massima
                    _bpm_buffer.append(bpm)
                    if len(_bpm_buffer) > _bpm_buffer_size:
                        _bpm_buffer.pop(0)
                    _last_peak_time = current_time
                    _last_peak_value = prev
                    # log("heart_rate", f"Peak accepted: BPM: {bpm:.1f}")
                    return bpm
            else:
                # Primo picco rilevato - stima iniziale 70 BPM
                _last_peak_time = current_time
                _last_peak_value = prev
                _estimated_bpm = 70  # Stima iniziale ragionevole
                _bpm_buffer.append(_estimated_bpm)
                # log("heart_rate", f"First peak detected - estimated BPM: {_estimated_bpm}")
                return _estimated_bpm
    
    return None

def _calculate_bpm():
    """Calcola BPM medio dal buffer"""
    if len(_bpm_buffer) < 1:  # Ridotto da 2 a 1 per output più veloce
        return None
    
    # Media degli ultimi BPM rilevati
    return sum(_bpm_buffer) / len(_bpm_buffer)

def _calculate_spo2():
    """Calcola SpO2 dal rapporto R"""
    global _spo2_buffer
    
    if len(_ir_buffer) < 50 or len(_red_buffer) < 50:
        return None
    
    # Calcola componenti DC e AC per IR e RED
    dc_ir = _calculate_dc_component(_ir_buffer)
    dc_red = _calculate_dc_component(_red_buffer)
    ac_ir = _calculate_ac_component(_ir_buffer, dc_ir)
    ac_red = _calculate_ac_component(_red_buffer, dc_red)
    
    # Verifica che i valori siano validi
    if dc_ir == 0 or dc_red == 0 or ac_ir == 0:
        return None
    
    # Calcola rapporto R = (AC_red/DC_red) / (AC_ir/DC_ir)
    r = (ac_red / dc_red) / (ac_ir / dc_ir)
    
    # Formula empirica per SpO2 (da letteratura MAX30102)
    # SpO2 = 110 - 25 * R
    spo2 = 110 - 25 * r
    
    # Filtra valori impossibili (SpO2 tra 70 e 100)
    if 70 <= spo2 <= 100:
        _spo2_buffer.append(spo2)
        
        # Mantieni buffer limitato
        if len(_spo2_buffer) > _spo2_buffer_size:
            _spo2_buffer.pop(0)
        
        # Ritorna media
        return sum(_spo2_buffer) / len(_spo2_buffer)
    
    return None

def read_heart_rate():
    global _readings_count, _ir_buffer, _red_buffer
    if _sensor is None:
        return
    if not elapsed("hr", 10):  # Lettura ogni 10ms per 100Hz
        return
    try:
        # Check for new data from sensor
        _sensor.check()
        
        # Check if data is available
        if not _sensor.available():
            return
        
        # Get IR and RED readings
        ir_value = _sensor.pop_ir_from_storage()
        red_value = _sensor.pop_red_from_storage()
        
        # Aggiungi ai buffer
        _ir_buffer.append(ir_value)
        _red_buffer.append(red_value)
        
        # Mantieni buffer di dimensione fissa
        if len(_ir_buffer) > _buffer_size:
            _ir_buffer.pop(0)
        if len(_red_buffer) > _buffer_size:
            _red_buffer.pop(0)
        
        # Increment readings counter
        _readings_count += 1
        
        # Store raw values in state
        state.sensor_data["heart_rate"]["ir"] = ir_value
        state.sensor_data["heart_rate"]["red"] = red_value
        
        # Calibra baseline se necessario
        if _baseline_ir == 0 and _readings_count > 20:
            if _calibrate_baseline():
                pass  # log("heart_rate", f"Baseline calibrated: IR={_baseline_ir:.0f}, threshold={_finger_threshold:.0f}")
        
        # Rileva presenza dito
        finger_detected = _detect_finger(ir_value)
        
        if not finger_detected:
            state.sensor_data["heart_rate"]["status"] = "No finger"
            state.sensor_data["heart_rate"]["bpm"] = None
            state.sensor_data["heart_rate"]["spo2"] = None
            
            # Reset buffers di calcolo
            global _last_peak_time, _bpm_buffer, _spo2_buffer
            _last_peak_time = 0
            _bpm_buffer.clear()
            _spo2_buffer.clear()
            
            # if _readings_count % 50 == 1:
            #     log("heart_rate", f"No finger (IR: {ir_value}, RED: {red_value})")
        else:
            state.sensor_data["heart_rate"]["status"] = "Reading"
            
            # Rileva picchi per BPM
            _detect_peak(ir_value)
            
            # Calcola BPM
            bpm = _calculate_bpm()
            if bpm:
                state.sensor_data["heart_rate"]["bpm"] = int(bpm)
            
            # Calcola SpO2 ogni 10 letture
            if _readings_count % 10 == 0:
                spo2 = _calculate_spo2()
                if spo2:
                    state.sensor_data["heart_rate"]["spo2"] = int(spo2)
            
            # Log periodico (disabled for unified logging)
            # if _readings_count % 20 == 0:
            #     bpm_str = f"{state.sensor_data['heart_rate']['bpm']} BPM" if bpm else "calculating..."
            #     spo2_str = f"{state.sensor_data['heart_rate']['spo2']}%" if state.sensor_data['heart_rate']['spo2'] else "calculating..."
            #     log("heart_rate", f"✓ IR: {ir_value:5d}, RED: {red_value:5d} | {bpm_str}, SpO2: {spo2_str}")
        
    except Exception as e:
        log("heart_rate", f"Read error: {e}")
        state.sensor_data["heart_rate"]["ir"] = None
        state.sensor_data["heart_rate"]["red"] = None
        state.sensor_data["heart_rate"]["status"] = "Error"
        _readings_count = 0
