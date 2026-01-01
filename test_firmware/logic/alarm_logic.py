"""Alarm logic module: evaluates sensor thresholds and manages multi-level alarms.

Each sensor can have states: normal, warning, danger (based on configured thresholds and timings).
Computes an overall alarm level based on all sensor states.
Sends commands to ESP32-B to update actuators when alarm level changes.
"""
import time

from config import config
from core import state
from core.timers import elapsed
from debug.debug import log
from comms import command_sender


# Internal timers for each monitored sensor
_alarm_timers = {
    "co": {"critical_start": None, "normal_start": None},
    "temp": {"critical_start": None, "normal_start": None},
    "heart": {"critical_start": None, "normal_start": None},
    "ultrasonic": {"critical_start": None, "normal_start": None},
}


def _update_alarm_level(kind, is_critical, warning_time, danger_time, recovery_time):
    """Updates multi-level alarm state for a sensor.

    Args:
        kind: 'co', 'temp', 'heart', 'ultrasonic'
        is_critical: instant critical condition (True/False)
        warning_time, danger_time, recovery_time: expressed in milliseconds
    """
    now = time.ticks_ms()
    timers = _alarm_timers[kind]

    level_key = kind + "_level"
    prev_level = state.system_state.get(level_key, "normal")

    if is_critical:
        timers["normal_start"] = None
        if timers["critical_start"] is None:
            timers["critical_start"] = now
        dt = time.ticks_diff(now, timers["critical_start"])

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
        dt = time.ticks_diff(now, timers["normal_start"])

        if recovery_time and dt >= recovery_time:
            level = "normal"
        else:
            level = prev_level

    if level != prev_level:
        state.system_state[level_key] = level
        log("alarm_logic", "update_alarm_level: [{}] {} -> {}".format(kind, prev_level, level))


def _update_overall_alarm():
    """Computes overall alarm level from individual sensor states."""
    prev_level = state.alarm_state.get("level", "normal")
    prev_source = state.alarm_state.get("source")

    levels = {
        "co": state.system_state.get("co_level", "normal"),
        "temp": state.system_state.get("temp_level", "normal"),
        "heart": state.system_state.get("heart_level", "normal"),
        "ultrasonic": state.system_state.get("ultrasonic_level", "normal"),
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
        
        # Send alarm command to ESP32-B to update actuators
        if command_sender.is_connected():
            command_sender.send_alarm_command(level, source)
        else:
            log("alarm_logic", "WARNING: ESP32-B not connected, cannot send alarm command")


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

    # Ultrasonic - presence detection (door/gate area)
    distance = state.sensor_data.get("ultrasonic_distance_cm")
    ultrasonic_critical = False
    if getattr(config, "ALARM_ULTRASONIC_ENABLED", True) and distance is not None:
        presence_dist = getattr(config, "ULTRASONIC_PRESENCE_DISTANCE_CM", 50.0)
        ultrasonic_critical = distance <= presence_dist
    _update_alarm_level(
        "ultrasonic",
        ultrasonic_critical,
        getattr(config, "ULTRASONIC_WARNING_TIME_MS", 2000),
        getattr(config, "ULTRASONIC_DANGER_TIME_MS", 10000),
        getattr(config, "ULTRASONIC_RECOVERY_TIME_MS", 5000),
    )

    # Overall alarm state
    _update_overall_alarm()
