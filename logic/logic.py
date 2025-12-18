import config, state
from timers import elapsed


def evaluate_logic():
    if not elapsed("logic", config.LOGIC_INTERVAL):
        return

    # CO
    state.system_state["alarm_co"] = (
        state.sensor_data["co"] is not None and
        state.sensor_data["co"] > config.CO_ALARM_THRESHOLD
    )

    # Temperature
    state.system_state["alarm_temp"] = (
        state.sensor_data["temperature"] is not None and
        state.sensor_data["temperature"] < config.TEMP_ALARM_THRESHOLD
    )

    # Movement (accelerometer)
    acc = state.sensor_data["acc"]
    state.system_state["movement"] = (
        abs(acc["x"]) > config.ACC_MOVEMENT_THRESHOLD or
        abs(acc["y"]) > config.ACC_MOVEMENT_THRESHOLD or
        abs(acc["z"]) > config.ACC_MOVEMENT_THRESHOLD
    )

    # Heart rate
    hr = state.sensor_data["heart_rate"]
    state.system_state["alarm_bpm"] = (
        hr["bpm"] is not None and
        (hr["bpm"] < config.BPM_LOW_THRESHOLD or hr["bpm"] > config.BPM_HIGH_THRESHOLD)
    )
    state.system_state["alarm_spo2"] = (
        hr["spo2"] is not None and
        hr["spo2"] < config.SPO2_THRESHOLD
    )
    