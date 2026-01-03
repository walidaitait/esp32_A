"""Heart rate sensor module (MAX30102).

Reads IR and RED LED reflectance data, detects finger presence,
and calculates BPM and SpO2 values.
"""
from machine import SoftI2C, Pin  # type: ignore
from time import ticks_ms, ticks_diff  # type: ignore
from sensors.libs.max30102 import MAX30102, MAX30105_PULSE_AMP_MEDIUM  # type: ignore
from config import config
from core import state
from core.timers import elapsed
from debug.debug import log

_i2c = None
_sensor = None
_readings_count = 0

# Buffers for signal analysis
_ir_buffer = []
_red_buffer = []
_buffer_size = 100  # 100 samples = 1 second at 100Hz

# Auto-calibration variables
_baseline_ir = 0
_baseline_red = 0
_finger_threshold = 5000  # Auto-calibrated threshold

# Variables for BPM calculation
_last_peak_time = 0
_last_peak_value = 0
_bpm_buffer = []
_bpm_buffer_size = 2  # Reduced to 2 for faster output
_estimated_bpm = None  # BPM estimate before second peak

# Variables for SpO2 calculation
_spo2_buffer = []
_spo2_buffer_size = 10

def init_heart_rate():
    global _i2c, _sensor
    try:
        log("heart_rate", "init_heart_rate: Initializing MAX30102 sensor...")
        
        # Setup I2C using SoftI2C
        _i2c = SoftI2C(
            sda=Pin(config.HEART_RATE_SDA_PIN),
            scl=Pin(config.HEART_RATE_SCL_PIN),
            freq=400000
        )
        
        log("heart_rate", "init_heart_rate: I2C initialized on SDA={}, SCL={}".format(config.HEART_RATE_SDA_PIN, config.HEART_RATE_SCL_PIN))
        
        # Scan I2C bus
        devices = _i2c.scan()
        log("heart_rate", "init_heart_rate: I2C scan found {} device(s): {}".format(len(devices), [hex(d) for d in devices]))
        
        # Create sensor instance
        _sensor = MAX30102(i2c=_i2c)
        log("heart_rate", "init_heart_rate: Sensor object created, expected address: {}".format(hex(_sensor.i2c_address)))
        
        # Check if sensor is detected on I2C bus
        if _sensor.i2c_address not in devices:
            log("heart_rate", "init_heart_rate: ERROR - Sensor not found at address {}".format(hex(_sensor.i2c_address)))
            log("heart_rate", "init_heart_rate: Check wiring - SDA, SCL, VCC, GND")
            log("heart_rate", "init_heart_rate: Try different I2C addresses if available")
            _sensor = None
            return False
        
        log("heart_rate", "init_heart_rate: Sensor found at address {}".format(hex(_sensor.i2c_address)))
        
        # Check part ID
        try:
            part_id_ok = _sensor.check_part_id()
            if not part_id_ok:
                log("heart_rate", "init_heart_rate: WARNING - Device ID does not match MAX30102/MAX30105")
                log("heart_rate", "init_heart_rate: Continuing anyway - might still work")
        except Exception as e:
            log("heart_rate", "init_heart_rate: WARNING - Could not check part ID: {}".format(e))
            log("heart_rate", "init_heart_rate: Continuing anyway...")
        
        # Setup sensor - optimal configuration for reading RED and IR
        log("heart_rate", "init_heart_rate: Configuring sensor...")
        _sensor.setup_sensor(
            led_mode=2,  # RED + IR mode (mode 2)
            adc_range=16384,  # Max ADC range for better resolution
            sample_rate=100,  # 100 samples/sec
            led_power=MAX30105_PULSE_AMP_MEDIUM,  # Medium LED power  
            sample_avg=8,  # Average 8 samples
            pulse_width=411  # Pulse width 411us - max sensitivity
        )
        
        log("heart_rate", "init_heart_rate: MAX30102 initialized successfully")
        return True
    except Exception as e:
        log("heart_rate", "init_heart_rate: Initialization failed: {}".format(e))
        import sys
        sys.print_exception(e)
        _sensor = None
        return False

def _calibrate_baseline():
    """Calibrate baseline when finger is not present."""
    global _baseline_ir, _baseline_red, _finger_threshold
    
    if len(_ir_buffer) < 20:
        return False
    
    # Calculate average of last 20 samples
    recent_ir = _ir_buffer[-20:]
    recent_red = _red_buffer[-20:]
    
    avg_ir = sum(recent_ir) / len(recent_ir)
    avg_red = sum(recent_red) / len(recent_red)
    
    # If values are low (<3000), it is baseline
    if avg_ir < 3000:
        _baseline_ir = avg_ir
        _baseline_red = avg_red
        _finger_threshold = _baseline_ir + 5000  # Threshold = baseline + 5000
        return True
    
    return False

def _detect_finger(ir_value):
    """Detect if finger is present on sensor."""
    global _finger_threshold
    
    # If not yet calibrated, use default threshold
    if _baseline_ir == 0:
        # Low values = no finger, high values = finger
        return ir_value > 5000
    
    # Use calibrated threshold
    return ir_value > _finger_threshold

def _calculate_dc_component(buffer):
    """Calculate DC component (average) of a buffer."""
    if len(buffer) < 10:
        return 0
    return sum(buffer[-50:]) / min(50, len(buffer))

def _calculate_ac_component(buffer, dc_value):
    """Calculate AC component (variation) of a buffer."""
    if len(buffer) < 10:
        return 0
    
    # AC = deviazione standard degli ultimi valori
    recent = buffer[-50:]
    variance = sum((x - dc_value) ** 2 for x in recent) / len(recent)
    return variance ** 0.5

def _detect_peak(ir_value):
    """Detect peaks to calculate BPM."""
    global _last_peak_time, _last_peak_value, _bpm_buffer, _estimated_bpm
    
    if len(_ir_buffer) < 3:
        return None
    
    # Use last 3 values to detect local maximum in real-time
    # [n-2, n-1, n] -> n-1 is peak if n-1 > n-2 and n-1 > n
    if len(_ir_buffer) >= 3:
        prev_prev = _ir_buffer[-3]
        prev = _ir_buffer[-2]
        current = _ir_buffer[-1]
        
        # Previous value is a peak if greater than both neighbors
        is_peak = prev > prev_prev and prev > current
        
        # Further reduced threshold for max sensitivity
        min_prominence = 30  # Reduced to 30 to detect more peaks
        is_prominent = (prev - prev_prev > min_prominence) and (prev - current > min_prominence)
        
        if is_peak and is_prominent:
            current_time = ticks_ms()
            
            # If we have a previous peak, calculate BPM
            if _last_peak_time > 0:
                time_diff = ticks_diff(current_time, _last_peak_time)
                
                # Very wide range for BPM (25-240)
                if 250 < time_diff < 2400:  # 250ms = 240BPM, 2400ms = 25BPM
                    bpm = 60000 / time_diff
                    _bpm_buffer.append(bpm)
                    
                    # Keep buffer limited
                    if len(_bpm_buffer) > _bpm_buffer_size:
                        _bpm_buffer.pop(0)
                    
                    _last_peak_time = current_time
                    _last_peak_value = prev
                    
                    # log("heart_rate", f"Peak detected! BPM: {bpm:.1f}, time_diff: {time_diff}ms")
                    return bpm
                else:
                    # Accept peak even if out of range
                    if time_diff > 2400:
                        bpm = 30  # Min estimate
                    else:
                        bpm = 240  # Max estimate
                    _bpm_buffer.append(bpm)
                    if len(_bpm_buffer) > _bpm_buffer_size:
                        _bpm_buffer.pop(0)
                    _last_peak_time = current_time
                    _last_peak_value = prev
                    # log("heart_rate", f"Peak accepted: BPM: {bpm:.1f}")
                    return bpm
            else:
                # First peak detected - use initial estimate 70 BPM
                _last_peak_time = current_time
                _last_peak_value = prev
                _estimated_bpm = 70  # Initial reasonable estimate
                _bpm_buffer.append(_estimated_bpm)
                # log("heart_rate", f"First peak detected - estimated BPM: {_estimated_bpm}")
                return _estimated_bpm
    
    return None

def _calculate_bpm():
    """Calculate average BPM from buffer."""
    if len(_bpm_buffer) < 1:  # Reduced from 2 to 1 for faster output
        return None
    
    # Average of latest detected BPMs
    return sum(_bpm_buffer) / len(_bpm_buffer)

def _calculate_spo2():
    """Calculate SpO2 from R ratio."""
    global _spo2_buffer
    
    if len(_ir_buffer) < 50 or len(_red_buffer) < 50:
        return None
    
    # Calculate DC and AC components for IR and RED
    dc_ir = _calculate_dc_component(_ir_buffer)
    dc_red = _calculate_dc_component(_red_buffer)
    ac_ir = _calculate_ac_component(_ir_buffer, dc_ir)
    ac_red = _calculate_ac_component(_red_buffer, dc_red)
    
    # Verify values are valid
    if dc_ir == 0 or dc_red == 0 or ac_ir == 0:
        return None
    
    # Calculate R ratio = (AC_red/DC_red) / (AC_ir/DC_ir)
    r = (ac_red / dc_red) / (ac_ir / dc_ir)
    
    # Empirical formula for SpO2 (from MAX30102 literature)
    # SpO2 = 110 - 25 * R
    spo2 = 110 - 25 * r
    
    # Filter impossible values (SpO2 between 70 and 100)
    if 70 <= spo2 <= 100:
        _spo2_buffer.append(spo2)
        
        # Keep buffer limited
        if len(_spo2_buffer) > _spo2_buffer_size:
            _spo2_buffer.pop(0)
        
        # Return average
        return sum(_spo2_buffer) / len(_spo2_buffer)
    
    return None

def read_heart_rate():
    global _readings_count, _ir_buffer, _red_buffer
    if _sensor is None:
        return
    if not elapsed("hr", 10):  # Read every 10ms for 100Hz
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
        
        # Add to buffers
        _ir_buffer.append(ir_value)
        _red_buffer.append(red_value)
        
        # Keep buffer at fixed size
        if len(_ir_buffer) > _buffer_size:
            _ir_buffer.pop(0)
        if len(_red_buffer) > _buffer_size:
            _red_buffer.pop(0)
        
        # Increment readings counter
        _readings_count += 1
        
        # Store raw values in state
        state.sensor_data["heart_rate"]["ir"] = ir_value
        state.sensor_data["heart_rate"]["red"] = red_value
        
        # Calibrate baseline if needed
        if _baseline_ir == 0 and _readings_count > 20:
            if _calibrate_baseline():
                pass
        
        # Detect finger presence
        finger_detected = _detect_finger(ir_value)
        
        if not finger_detected:
            state.sensor_data["heart_rate"]["status"] = "No finger"
            state.sensor_data["heart_rate"]["bpm"] = None
            state.sensor_data["heart_rate"]["spo2"] = None
            
            # Reset calculation buffers
            global _last_peak_time, _bpm_buffer, _spo2_buffer
            _last_peak_time = 0
            _bpm_buffer.clear()
            _spo2_buffer.clear()
        else:
            state.sensor_data["heart_rate"]["status"] = "Reading"
            
            # Detect peaks for BPM
            _detect_peak(ir_value)
            
            # Calculate BPM
            bpm = _calculate_bpm()
            if bpm:
                state.sensor_data["heart_rate"]["bpm"] = int(bpm)
            
            # Calculate SpO2 every 10 readings
            if _readings_count % 10 == 0:
                spo2 = _calculate_spo2()
                if spo2:
                    state.sensor_data["heart_rate"]["spo2"] = int(spo2)
        
    except Exception as e:
        log("heart_rate", "read_heart_rate: Read error: {}".format(e))
        state.sensor_data["heart_rate"]["ir"] = None
        state.sensor_data["heart_rate"]["red"] = None
        state.sensor_data["heart_rate"]["status"] = "Error"
        _readings_count = 0
