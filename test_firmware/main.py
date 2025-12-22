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
# from sensors import accelerometer  # DISABLED
from sensors import ultrasonic
from sensors import heart_rate
from sensors import buttons

# System info display interval (every 3 seconds for all sensors)
PRINT_INTERVAL = 3000
_last_print = 0

def init_sensors():
    """Initialize all sensors - gracefully handle failures"""
    print("\n" + "="*50)
    print("TEST FIRMWARE - MULTI-SENSOR MONITORING")
    print("="*50)
    
    sensors_status = {
        "Temperature": temperature.init_temperature(),
        "CO Sensor": co.init_co(),
        # "Accelerometer": accelerometer.init_accelerometer(),  # DISABLED
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
    # accelerometer.read_accelerometer()  # DISABLED
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
    
    print("\n" + "="*60)
    print(f"SENSOR DATA @ {now}ms")
    print("="*60)
    
    # Temperature
    temp = state.sensor_data.get("temperature", None)
    if temp is not None:
        print(f"Temperature:  {temp:.2f} °C")
    else:
        print(f"Temperature:  N/A")
    
    # CO (Carbon Monoxide)
    co = state.sensor_data.get("co", None)
    if co is not None:
        print(f"CO Level:     {co:.2f} PPM")
        if co < 9:
            print(f"  Status:     Safe (< 9 PPM)")
        elif co < 50:
            print(f"  Status:     Warning (9-50 PPM)")
        else:
            print(f"  Status:     Danger! (> 50 PPM)")
    else:
        print(f"CO Level:     N/A")
    
    # Ultrasonic Distance
    distance = state.sensor_data.get("ultrasonic_distance_cm", None)
    if distance is not None:
        print(f"Distance:     {distance:.2f} cm ({distance/100:.2f} m)")
        if distance < 10:
            print(f"  Status:     Very Close (< 10cm)")
        elif distance < 50:
            print(f"  Status:     Close (10-50cm)")
        elif distance < 100:
            print(f"  Status:     Medium (50-100cm)")
        else:
            print(f"  Status:     Far (> 100cm)")
    else:
        print(f"Distance:     N/A")
    
    # Heart Rate
    hr_data = state.sensor_data.get("heart_rate", {})
    hr_status = hr_data.get("status", "N/A")
    hr_bpm = hr_data.get("bpm", None)
    hr_spo2 = hr_data.get("spo2", None)
    hr_ir = hr_data.get("ir", None)
    hr_red = hr_data.get("red", None)
    
    print(f"Heart Rate:   ", end="")
    if hr_status == "Reading" and hr_bpm:
        print(f"{hr_bpm} BPM")
    elif hr_status == "Reading":
        print(f"Calculating...")
    else:
        print(f"{hr_status}")
    
    if hr_spo2:
        print(f"SpO2:         {hr_spo2}%")
    
    if hr_ir and hr_red:
        print(f"  Raw:        IR={hr_ir}, RED={hr_red}")
    
    # Buttons
    b1_state = state.button_state.get("b1", False)
    b2_state = state.button_state.get("b2", False)
    b3_state = state.button_state.get("b3", False)
    
    print(f"Buttons:      B1={'PRESSED' if b1_state else 'released'}  " +
          f"B2={'PRESSED' if b2_state else 'released'}  " +
          f"B3={'PRESSED' if b3_state else 'released'}")
    
    print("="*60 + "\n")

def main():
    """Main test firmware loop"""
    print("\n" + "#"*60)
    print("#  ESP32 TEST FIRMWARE - MULTI-SENSOR MONITORING")
    print("#  Version: 2.0")
    print("#  Active Sensors: Temperature, CO, Ultrasonic, Heart Rate, Buttons")
    print("#  Disabled: Accelerometer")
    print("#"*60 + "\n")
    
    # Initialize sensors
    init_sensors()
    
    print("Starting main loop...")
    print("Sensor data will be printed every 3 seconds.\n")
    
    # Main loop
    while True:
        try:
            # Read all sensors (non-blocking)
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
