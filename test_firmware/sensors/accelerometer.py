\"\"\"Accelerometer sensor module.\n\nReads 3-axis accelerometer data via ADC.\n\"\"\"\nfrom machine import ADC, Pin  # type: ignore\nimport config, state\nfrom timers import elapsed\nfrom debug import log\nimport time\n\n_adc_x = None\n_adc_y = None\n_adc_z = None\n_sensor_connected = False\n\ndef init_accelerometer():\n    global _adc_x, _adc_y, _adc_z, _sensor_connected\n    try:\n        _adc_x = ADC(Pin(config.ACC_X_PIN))\n        _adc_y = ADC(Pin(config.ACC_Y_PIN))\n        _adc_z = ADC(Pin(config.ACC_Z_PIN))\n\n        for adc in (_adc_x, _adc_y, _adc_z):\n            adc.atten(ADC.ATTN_11DB)\n        \n        # Check if sensor is actually connected (non-blocking)\n        voltages = []\n        for adc in (_adc_x, _adc_y, _adc_z):\n            adc_val = adc.read()\n            voltage = adc_val * 3.3 / 4095\n            voltages.append(voltage)\n        \n        valid_readings = 0\n        for v in voltages:\n            if 0.8 < v < 2.5:  # Realistic range for resting accelerometer\n                valid_readings += 1\n        \n        if valid_readings >= 2:  # At least 2 axes must read valid values\n            _sensor_connected = True\n            log(\"accelerometer\", \"init_accelerometer: Accelerometer initialized and detected\")\n            return True\n        else:\n            log(\"accelerometer\", \"init_accelerometer: Sensor not detected (voltages: {})\".format(voltages))\n            _adc_x = None\n            _adc_y = None\n            _adc_z = None\n            _sensor_connected = False\n            return False\n            \n    except Exception as e:\n        log(\"accelerometer\", \"init_accelerometer: Initialization failed: {}\".format(e))\n        _adc_x = None\n        _adc_y = None\n        _adc_z = None\n        _sensor_connected = False\n        return False

def read_accelerometer():
    if not _sensor_connected or _adc_x is None or _adc_y is None or _adc_z is None:
        return
    if not elapsed("acc", config.ACC_INTERVAL):
        return

    try:
        for axis, adc in [("x", _adc_x), ("y", _adc_y), ("z", _adc_z)]:
            adc_val = adc.read()
            voltage = adc_val * 3.3 / 4095
            g = (voltage - 1.65) / 0.3
            state.sensor_data["acc"][axis] = round(g, 2)
    except Exception as e:
        log("accelerometer", "read_accelerometer: Read error: {}".format(e))
