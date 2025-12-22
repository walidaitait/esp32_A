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
from sensors import temperature
from sensors import co
from sensors import accelerometer
from sensors import ultrasonic
from sensors import heart_rate
from sensors import buttons

# System info display interval (every 5 seconds)
PRINT_INTERVAL = 5000
_last_print = 0

def init_sensors():
    """Initialize all sensors - gracefully handle failures"""
    print("\n" + "="*50)
    print("TEST FIRMWARE - SENSOR INITIALIZATION")
    print("="*50)
    
    sensors_status = {
        "Temperature": temperature.init_temperature(),
        "CO Sensor": co.init_co(),
        "Accelerometer": accelerometer.init_accelerometer(),
        "Ultrasonic": ultrasonic.init_ultrasonic(),
        "Heart Rate": heart_rate.init_heart_rate(),
        "Buttons": buttons.init_buttons()
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
    temperature.read_temperature()
    co.read_co()
    accelerometer.read_accelerometer()
    ultrasonic.read_ultrasonic()
    heart_rate.read_heart_rate()
    buttons.read_buttons()

def print_sensor_data():
    """Print current sensor data in a readable format"""
    global _last_print
    now = time.ticks_ms()
    
    if time.ticks_diff(now, _last_print) < PRINT_INTERVAL:
        return
    
    _last_print = now
    
    print("\n" + "="*50)
    print(f"SENSOR DATA @ {now}ms")
    print("="*50)
    
    # Temperature
    temp = state.sensor_data.get("temperature")
    print(f"Temperature:  {temp if temp is not None else 'N/A'} °C")
    
    # CO
    co_val = state.sensor_data.get("co")
    print(f"CO Level:     {co_val if co_val is not None else 'N/A'} PPM")
    
    # Accelerometer
    acc = state.sensor_data.get("acc", {})
    x = acc.get("x", "N/A")
    y = acc.get("y", "N/A")
    z = acc.get("z", "N/A")
    print(f"Accelerometer: X={x}g, Y={y}g, Z={z}g")
    
    # Ultrasonic
    distance = state.sensor_data.get("ultrasonic_distance_cm")
    print(f"Distance:     {distance if distance is not None else 'N/A'} cm")
    
    # Heart Rate
    hr = state.sensor_data.get("heart_rate", {})
    bpm = hr.get("bpm", "N/A")
    spo2 = hr.get("spo2", "N/A")
    print(f"Heart Rate:   BPM={bpm}, SpO2={spo2}%")
    
    # Buttons
    buttons_state = state.button_state
    b1 = "PRESSED" if buttons_state.get("b1") else "Released"
    b2 = "PRESSED" if buttons_state.get("b2") else "Released"
    b3 = "PRESSED" if buttons_state.get("b3") else "Released"
    print(f"Buttons:      B1={b1}, B2={b2}, B3={b3}")
    
    print("="*50 + "\n")

def main():
    """Main test firmware loop"""
    print("\n" + "#"*50)
    print("#  ESP32 TEST FIRMWARE - SENSORS ONLY")
    print("#  Version: 1.0")
    print("#  Purpose: Test sensors without complexity")
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
