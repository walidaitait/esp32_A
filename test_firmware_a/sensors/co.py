"""Carbon monoxide (CO) sensor driver module (DFRobot MQ-7).

Imported by: core.sensor_loop
Imports: machine.ADC, machine.Pin, time, config.config, core.state, 
         core.timers, debug.debug

Reads analog CO levels from MQ-7 sensor and converts to PPM (parts per million).

Key features:
- Fast baseline calibration: Takes short initial baseline (2s default) instead
  of requiring long burn-in time
- Adaptive baseline: Slowly tracks sensor drift over time (1% per reading)
- Configurable sensitivity: PPM/V ratio, baseline window, guard threshold
- Clamping: Prevents unrealistic high readings
- Offset correction: Optional static offset for calibration

Algorithm:
1. During baseline window: Average raw readings, report 0 PPM
2. After baseline: Calculate delta from baseline voltage
3. Apply guard threshold to ignore noise
4. Convert voltage delta to PPM using linear scaling
5. Clamp to maximum realistic value

This approach provides stable readings even with short boot times,
avoiding the fixed ~100 PPM offset without requiring long warm-up.
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
_read_count = 0

def init_co():
    global _adc, _baseline_mv, _baseline_samples, _baseline_start_ms
    try:
        _adc = ADC(Pin(config.CO_PIN))
        _adc.atten(ADC.ATTN_11DB)
        _baseline_mv = None
        _baseline_samples = 0
        _baseline_start_ms = ticks_ms()
        log("sensor.co", "init_co: CO sensor initialized")
        return True
    except Exception as e:
        log("sensor.co", "init_co: Initialization failed: {}".format(e))
        _adc = None
        return False

def _adc_to_mv(raw_value):
    # Convert raw ADC value to millivolts assuming 3.3V reference
    return (raw_value * 3300) / 4095


def read_co():
    global _baseline_mv, _baseline_samples, _baseline_start_ms, _read_count
    if _adc is None:
        return
    if not elapsed("co", config.CO_INTERVAL):
        return

    try:
        _read_count += 1
        raw = _adc.read()
        mv = _adc_to_mv(raw)

        # Configurable parameters with safe defaults
        baseline_ms = getattr(config, "CO_BASELINE_MS", 2000)  # short baseline window
        guard_mv = getattr(config, "CO_MIN_GUARD_MV", 3)       # ignore tiny noise
        ppm_per_v = getattr(config, "CO_PPM_PER_V", 400)       # ppm per volt over baseline
        clamp_max = getattr(config, "CO_PPM_CLAMP", 300)       # clamp maximum reported ppm
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
            if _read_count % 10 == 0:
                log("sensor.co", "baseline phase raw={} mv={:.1f} samples={} avg={:.1f}".format(raw, mv, _baseline_samples, _baseline_mv))
            return

        # If baseline was never set (edge cases), set it now
        if _baseline_mv is None:
            _baseline_mv = mv

        # Lightly refresh baseline to follow slow drift without heavy math
        _baseline_mv = (_baseline_mv * 0.99) + (mv * 0.01)

        # Delta from baseline
        delta_mv = mv - _baseline_mv - offset_mv
        if delta_mv < guard_mv:
            delta_mv = 0

        ppm = (delta_mv / 1000.0) * ppm_per_v
        ppm = max(0.0, min(clamp_max, ppm))

        state.sensor_data["co"] = round(ppm, 2)

        if _read_count % 10 == 0:
            actual_delta = mv - _baseline_mv - offset_mv  # Show unfiltered delta for diagnostics
            # Disabled: log("co", "read raw={} mv={:.1f} baseline={:.1f} delta_raw={:.1f} delta_filt={:.1f} ppm={:.2f}".format(
            #     raw, mv, _baseline_mv, actual_delta, delta_mv, ppm
            # ))
    except Exception as e:
        log("sensor.co", "read_co: Read error: {}".format(e))
        state.sensor_data["co"] = None
