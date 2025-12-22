"""
TEST FIRMWARE - Sensors Only
Simplified firmware to test sensors without logic/communication complexity
OTA update system remains active for remote updates
"""

# Import OTA first and check for updates BEFORE importing anything else
import ota_update
ota_update.check_and_update()

# Now import everything else (only after OTA check)
import time
from debug import log
import state

# Sensor modules
# from sensors import temperature
# from sensors import co
# from sensors import accelerometer
# from sensors import ultrasonic
from sensors import heart_rate
# from sensors import buttons

# System info display interval (every 2 seconds for better heart rate monitoring)
PRINT_INTERVAL = 2000
_last_print = 0

def init_sensors():
    """Initialize all sensors - gracefully handle failures"""
    print("\n" + "="*50)
    print("TEST FIRMWARE - HEART RATE SENSOR ONLY")
    print("="*50)
    
    sensors_status = {
        # "Temperature": temperature.init_temperature(),
        # "CO Sensor": co.init_co(),
        # "Accelerometer": accelerometer.init_accelerometer(),
        # "Ultrasonic": ultrasonic.init_ultrasonic(),
        "Heart Rate": heart_rate.init_heart_rate(),
        # "Buttons": buttons.init_buttons()
    }
    
    print("\n" + "-"*50)
    print("INITIALIZATION SUMMARY:")
    for name, status in sensors_status.items():
        status_str = "OK" if status else "FAILED/NOT CONNECTED"
        print(f"  {name:20s}: {status_str}")
    print("-"*50 + "\n")
    
    return sensors_status

def read_sensors():
    """Read all sensors - non-blocking"""
    # temperature.read_temperature()
    # co.read_co()
    # accelerometer.read_accelerometer()
    # ultrasonic.read_ultrasonic()
    heart_rate.read_heart_rate()
    # buttons.read_buttons()

def print_sensor_data():
    """Print current sensor data in a readable format"""
    global _last_print
    now = time.ticks_ms()
    
    if time.ticks_diff(now, _last_print) < PRINT_INTERVAL:
        return
    
    _last_print = now
    
    print("\n" + "="*50)
    print(f"HEART RATE SENSOR DATA @ {now}ms")
    print("="*50)
    
    # Heart Rate Only
    hr = state.sensor_data.get("heart_rate", {})
    bpm = hr.get("bpm", "N/A")
    spo2 = hr.get("spo2", "N/A")
    print(f"Heart Rate:   BPM={bpm}")
    print(f"SpO2:         {spo2}%")
    
    print("="*50 + "\n")

def main():
    """Main test firmware loop"""
    print("\n" + "#"*50)
    print("#  ESP32 TEST FIRMWARE - HEART RATE ONLY")
    print("#  Version: 1.0")
    print("#  Purpose: Test heart rate sensor only")
    print("#"*50 + "\n")
    
    # Initialize sensors
    init_sensors()
    
    print("Starting main loop...")
    print("Sensor data will be printed every 5 seconds.\n")
    
    # Main loop
    while True:
        try:
            # Read all sensors
            read_sensors()
            
            # Print sensor data periodically
            print_sensor_data()
            
            # Small delay to prevent CPU overload
            time.sleep_ms(10)
            
        except KeyboardInterrupt:
            print("\nTest firmware stopped by user.")
            break
        except Exception as e:
            print(f"\nERROR in main loop: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
