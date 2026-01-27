"""Multi-level alarm logic evaluation module.

Imported by: core.sensor_loop
Imports: time (MicroPython), config.config, core.state, core.timers, debug.debug

Evaluates sensor readings against thresholds and manages three-level alarms:
- normal: All values within safe ranges
- warning: Value exceeded threshold for warning_time duration
- danger: Value exceeded threshold for danger_time duration

Key features:
- Per-sensor alarm levels (CO, temperature, heart rate tracked separately)
- Time-based windows prevent false alarms from transient spikes
- Recovery delays prevent alarm flapping
- Overall system alarm computed from worst individual sensor state
- Presence detection for gate automation (not alarm-based)
- Event notifications sent to Board B on critical state changes

Architecture:
1. evaluate_logic() called periodically (200ms default) from sensor_loop
2. Each sensor checked against instant thresholds (CO PPM, temp range, HR range, SpO2)
3. _update_alarm_level() tracks how long threshold exceeded
4. After warning_time: sensor enters "warning" state
5. After danger_time: sensor enters "danger" state
6. Recovery timer required before returning to "normal"
7. _update_overall_alarm() aggregates worst state (danger > warning > normal)
8. Urgent publish requested to Node-RED when entering warning/danger

Thresholds (configurable in config.json):
- CO: 50 PPM critical (warning 5s, danger 30s, recovery 10s)
- Temperature: <10\u00b0C or >35\u00b0C critical (warning 10s, danger 60s, recovery 15s)
- Heart rate: <50 or >120 BPM, or SpO2 <90% (warning 10s, danger 60s, recovery 15s)

Ultrasonic presence is tracked but does NOT trigger alarms.
It sets presence_detected flag used by Board B for gate automation.
"""
from time import ticks_ms, ticks_diff  # type: ignore

from config import config
from core import state
from core.timers import elapsed
from debug.debug import log


# Internal timers for each monitored sensor (ultrasonic is presence-only, no alarm timers)
_alarm_timers = {
    "co": {"critical_start": None, "normal_start": None},
    "temp": {"critical_start": None, "normal_start": None},
    "heart": {"critical_start": None, "normal_start": None},
}


def _update_alarm_level(kind, is_critical, warning_time, danger_time, recovery_time):
    """Updates multi-level alarm state for a sensor.

    Args:
        kind: 'co', 'temp', 'heart'
        is_critical: instant critical condition (True/False)
        warning_time, danger_time, recovery_time: expressed in milliseconds
    """
    now = ticks_ms()
    timers = _alarm_timers[kind]

    level_key = kind + "_level"
    prev_level = state.system_state.get(level_key, "normal")

    if is_critical:
        timers["normal_start"] = None
        if timers["critical_start"] is None:
            timers["critical_start"] = now
        dt = ticks_diff(now, timers["critical_start"])

        if danger_time and dt >= danger_time:
            level = "danger"
        elif warning_time and dt >= warning_time:
            level = "warning"
        else:
            level = prev_level
    else:
        timers["critical_start"] = None
        if timers["normal_start"] is None:
            timers["normal_start"] = now
        dt = ticks_diff(now, timers["normal_start"])

        if recovery_time and dt >= recovery_time:
            level = "normal"
        else:
            level = prev_level

    if level != prev_level:
        state.system_state[level_key] = level
        log("alarm.logic", "update_alarm_level: [{}] {} -> {}".format(kind, prev_level, level))


def _update_overall_alarm():
    """Computes overall alarm level from individual sensor states."""
    prev_level = state.alarm_state.get("level", "normal")
    prev_source = state.alarm_state.get("source")

    levels = {
        "co": state.system_state.get("co_level", "normal"),
        "temp": state.system_state.get("temp_level", "normal"),
        "heart": state.system_state.get("heart_level", "normal"),
    }

    level = "normal"
    source = None

    for name, sensor_level in levels.items():
        if sensor_level == "danger":
            level = "danger"
            source = name
            break
        if sensor_level == "warning" and level == "normal":
            level = "warning"
            source = name

    state.alarm_state["level"] = level
    state.alarm_state["source"] = source

    if level != prev_level or source != prev_source:
        log(
            "alarm_logic",
            "update_overall_alarm: {}:{} -> {}:{}".format(
                prev_level, prev_source, level, source
            ),
        )
        
        # If alarm level changed to warning or danger, request immediate publish (handled in nodered_client.update)
        if level in ("warning", "danger"):
            try:
                from communication import nodered_client
                nodered_client.request_publish_now()
                log("alarm_logic", "Requested urgent alarm state publish to Node-RED")
            except Exception as e:
                log("alarm_logic", "Failed to request urgent state publish: {}".format(e))


def evaluate_logic():
    """Periodically evaluates sensor warning/danger states.

    Non-blocking: called frequently from main loop but performs real work
    only every LOGIC_INTERVAL ms.
    """
    if not hasattr(config, "LOGIC_INTERVAL"):
        return

    if not elapsed("logic", config.LOGIC_INTERVAL):
        return

    # CO - carbon monoxide level (PPM)
    co_value = state.sensor_data.get("co")
    co_critical = False
    if getattr(config, "ALARM_CO_ENABLED", True) and co_value is not None:
        co_critical = co_value >= getattr(config, "CO_CRITICAL_PPM", 50.0)
    _update_alarm_level(
        "co",
        co_critical,
        getattr(config, "CO_WARNING_TIME_MS", 5000),
        getattr(config, "CO_DANGER_TIME_MS", 30000),
        getattr(config, "CO_RECOVERY_TIME_MS", 10000),
    )

    # House temperature
    temp_value = state.sensor_data.get("temperature")
    temp_critical = False
    if getattr(config, "ALARM_TEMP_ENABLED", True) and temp_value is not None:
        low = getattr(config, "TEMP_MIN_SAFE", 10.0)
        high = getattr(config, "TEMP_MAX_SAFE", 35.0)
        temp_critical = temp_value < low or temp_value > high
    _update_alarm_level(
        "temp",
        temp_critical,
        getattr(config, "TEMP_WARNING_TIME_MS", 10000),
        getattr(config, "TEMP_DANGER_TIME_MS", 60000),
        getattr(config, "TEMP_RECOVERY_TIME_MS", 15000),
    )

    # Heart rate + SpO2
    hr = state.sensor_data.get("heart_rate", {})
    heart_critical = False
    if getattr(config, "ALARM_HEART_ENABLED", True):
        bpm = hr.get("bpm")
        spo2 = hr.get("spo2")
        if bpm is not None:
            low = getattr(config, "BPM_LOW_THRESHOLD", 50)
            high = getattr(config, "BPM_HIGH_THRESHOLD", 120)
            if bpm < low or bpm > high:
                heart_critical = True
        if spo2 is not None:
            spo2_thr = getattr(config, "SPO2_THRESHOLD", 90)
            if spo2 < spo2_thr:
                heart_critical = True
    _update_alarm_level(
        "heart",
        heart_critical,
        getattr(config, "HR_WARNING_TIME_MS", 10000),
        getattr(config, "HR_DANGER_TIME_MS", 60000),
        getattr(config, "HR_RECOVERY_TIME_MS", 15000),
    )

    # Ultrasonic - presence-only (no alarms). Note presence up to threshold distance.
    distance = state.sensor_data.get("ultrasonic_distance_cm")
    presence_dist = getattr(config, "ULTRASONIC_PRESENCE_DISTANCE_CM", 50.0)
    presence = distance is not None and distance <= presence_dist
    state.sensor_data["ultrasonic_presence"] = presence
    
    # Update gate control state
    prev_presence = state.gate_state.get("presence_detected", False)
    state.gate_state["presence_detected"] = presence
    
    # If presence was lost, record the time for delayed gate close
    if prev_presence and not presence:
        state.gate_state["last_presence_lost_ms"] = ticks_ms()
        log("alarm.logic", "Gate: presence lost, will close after delay")
    elif not prev_presence and presence:
        state.gate_state["last_presence_lost_ms"] = None
        log("alarm.logic", "Gate: presence detected, opening gate")

    # Overall alarm state
    _update_overall_alarm()
