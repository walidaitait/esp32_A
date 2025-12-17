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
    