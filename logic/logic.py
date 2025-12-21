import config, state
from timers import elapsed
from logic import hooks


def evaluate_logic():
    if not elapsed("logic", config.LOGIC_INTERVAL):
        return

    prev = state.system_state.copy()

    # CO
    state.system_state["alarm_co"] = (
        state.sensor_data["co"] is not None and
        state.sensor_data["co"] > config.CO_ALARM_THRESHOLD
    )

    # Temperature (note: current logic uses < threshold; keep as-is)
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

    # Fire hooks on transitions only
    if state.system_state["alarm_co"] != prev["alarm_co"]:
        hooks.on_alarm_change("co", state.system_state["alarm_co"], state.sensor_data["co"])

    if state.system_state["alarm_temp"] != prev["alarm_temp"]:
        hooks.on_alarm_change("temperature", state.system_state["alarm_temp"], state.sensor_data["temperature"])

    if state.system_state["alarm_bpm"] != prev["alarm_bpm"]:
        hooks.on_alarm_change("heart_rate_bpm", state.system_state["alarm_bpm"], state.sensor_data["heart_rate"]["bpm"])

    if state.system_state["alarm_spo2"] != prev["alarm_spo2"]:
        hooks.on_alarm_change("heart_rate_spo2", state.system_state["alarm_spo2"], state.sensor_data["heart_rate"]["spo2"])

    if state.system_state["movement"] != prev["movement"]:
        hooks.on_movement_change(state.system_state["movement"], dict(acc))
    