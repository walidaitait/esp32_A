"""Carbon monoxide sensor module (DFRobot MQ-7).

Goal: provide stable readings even if the board stays on only a few
seconds. We take a short startup baseline and compute ppm as delta from
that baseline. This avoids the fixed ~100 ppm offset without requiring
long burn-in.
"""
from machine import ADC, Pin  # type: ignore
from time import ticks_ms, ticks_diff  # type: ignore
from config import config
from core import state
from core.timers import elapsed
from debug.debug import log

_adc = None
_baseline_mv = None  # Baseline in millivolts
_baseline_samples = 0
_baseline_start_ms = 0

def init_co():
    global _adc, _baseline_mv, _baseline_samples, _baseline_start_ms
    try:
        _adc = ADC(Pin(config.CO_PIN))
        _adc.atten(ADC.ATTN_11DB)
        _baseline_mv = None
        _baseline_samples = 0
        _baseline_start_ms = ticks_ms()
        log("co", "init_co: CO sensor initialized")
        return True
    except Exception as e:
        log("co", "init_co: Initialization failed: {}".format(e))
        _adc = None
        return False

def _adc_to_mv(raw_value):
    # Convert raw ADC value to millivolts assuming 3.3V reference
    return (raw_value * 3300) / 4095


def read_co():
    global _baseline_mv, _baseline_samples, _baseline_start_ms
    if _adc is None:
        return
    if not elapsed("co", config.CO_INTERVAL):
        return

    try:
        raw = _adc.read()
        mv = _adc_to_mv(raw)

        # Configurable parameters with safe defaults
        baseline_ms = getattr(config, "CO_BASELINE_MS", 4000)  # short baseline window
        guard_mv = getattr(config, "CO_MIN_GUARD_MV", 20)      # ignore deltas below this noise floor
        ppm_per_volt = getattr(config, "CO_PPM_PER_V", 400)    # ppm per volt over baseline
        clamp_max = getattr(config, "CO_PPM_CLAMP", 500)       # clamp maximum reported ppm
        offset_mv = getattr(config, "CO_OFFSET_MV", 0)         # optional offset after baseline

        now = ticks_ms()
        if ticks_diff(now, _baseline_start_ms) < baseline_ms:
            # Baseline phase: average early readings, report 0 ppm
            if _baseline_mv is None:
                _baseline_mv = mv
                _baseline_samples = 1
            else:
                _baseline_samples += 1
                _baseline_mv = (_baseline_mv * (_baseline_samples - 1) + mv) / _baseline_samples
            state.sensor_data["co"] = 0.0
            return

        # If baseline was never set (edge cases), set it now
        if _baseline_mv is None:
            _baseline_mv = mv

        # Delta from baseline
        delta_mv = mv - _baseline_mv - offset_mv
        if delta_mv < guard_mv:
            delta_mv = 0

        ppm = (delta_mv / 1000.0) * ppm_per_volt
        ppm = max(0.0, min(clamp_max, ppm))

        state.sensor_data["co"] = round(ppm, 2)
    except Exception as e:
        log("co", "read_co: Read error: {}".format(e))
        state.sensor_data["co"] = None
