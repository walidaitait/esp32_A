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
from sensors import ultrasonic
# from sensors import heart_rate
# from sensors import buttons

# System info display interval (every 500ms for ultrasonic monitoring)
PRINT_INTERVAL = 500
_last_print = 0

def init_sensors():
    """Initialize all sensors - gracefully handle failures"""
    print("\n" + "="*50)
    print("TEST FIRMWARE - ULTRASONIC SENSOR ONLY (HC-SR04)")
    print("="*50)
    
    sensors_status = {
        # "Temperature": temperature.init_temperature(),
        # "CO Sensor": co.init_co(),
        # "Accelerometer": accelerometer.init_accelerometer(),
        "Ultrasonic": ultrasonic.init_ultrasonic(),
        # "Heart Rate": heart_rate.init_heart_rate(),
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
    ultrasonic.read_ultrasonic()
    # heart_rate.read_heart_rate()
    # buttons.read_buttons()

def print_sensor_data():
    """Print current sensor data in a readable format"""
    global _last_print
    now = time.ticks_ms()
    
    if time.ticks_diff(now, _last_print) < PRINT_INTERVAL:
        return
    
    _last_print = now
    
    print("\n" + "="*50)
    print(f"ULTRASONIC SENSOR DATA @ {now}ms")
    print("="*50)
    
    # Ultrasonic Distance
    distance = state.sensor_data.get("ultrasonic_distance_cm", None)
    
    if distance is not None:
        print(f"Distance:     {distance:.2f} cm ({distance/100:.2f} m)")
        
        # Aggiungi indicatori di prossimità
        if distance < 5:
            print(f"Status:       🔴 MOLTO VICINO! (<5cm)")
        elif distance < 10:
            print(f"Status:       🟠 Vicino (5-10cm)")
        elif distance < 30:
            print(f"Status:       🟡 Medio (10-30cm)")
        elif distance < 100:
            print(f"Status:       🟢 Lontano (30-100cm)")
        elif distance < 200:
            print(f"Status:       🔵 Molto lontano (100-200cm)")
        else:
            print(f"Status:       ⚪ Oltre 2 metri")
    else:
        print(f"Distance:     N/A (no reading)")
        print(f"Status:       ⚠️  No signal or out of range")
    
    print("="*50 + "\n")

def main():
    """Main test firmware loop"""
    print("\n" + "#"*50)
    print("#  ESP32 TEST FIRMWARE - ULTRASONIC ONLY")
    print("#  Version: 1.0")
    print("#  Purpose: Test HC-SR04 ultrasonic sensor")
    print("#  Pins: TRIG=GPIO5, ECHO=GPIO18")
    print("#"*50 + "\n")
    
    # Initialize sensors
    init_sensors()
    
    print("Starting main loop...")
    print("Sensor data will be printed every 0.5 seconds.\n")
    print("Place an object in front of the sensor to test distance measurement.\n")
    
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
