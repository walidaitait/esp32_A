from machine import SoftI2C, Pin  # type: ignore
from sensors.libs.max30102 import MAX30102, MAX30105_PULSE_AMP_MEDIUM  # type: ignore
import config, state
from timers import elapsed
from debug import log
import time

_i2c = None
_sensor = None
_readings_count = 0

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

def read_heart_rate():
    global _readings_count
    if _sensor is None:
        return
    if not elapsed("hr", 100):  # Lettura ogni 100ms
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
        
        # Increment readings counter
        _readings_count += 1
        
        # Store values in state (per compatibilità con main.py)
        state.sensor_data["heart_rate"]["ir"] = ir_value
        state.sensor_data["heart_rate"]["red"] = red_value
        
        # Check if finger is present (IR value should be > 50000 for good contact)
        if ir_value < 50000:
            state.sensor_data["heart_rate"]["status"] = "No finger"
            if _readings_count % 10 == 1:  # Log ogni 10 letture solo la prima volta
                log("heart_rate", f"No finger detected (IR: {ir_value}, RED: {red_value})")
        else:
            state.sensor_data["heart_rate"]["status"] = "Reading"
            # Log periodicamente i valori quando il dito è presente
            if _readings_count % 5 == 0:  # Log ogni 5 letture
                log("heart_rate", f"✓ IR: {ir_value:6d}, RED: {red_value:6d} (reading #{_readings_count})")
        
    except Exception as e:
        log("heart_rate", f"Read error: {e}")
        state.sensor_data["heart_rate"]["ir"] = None
        state.sensor_data["heart_rate"]["red"] = None
        state.sensor_data["heart_rate"]["status"] = "Error"
        _readings_count = 0
