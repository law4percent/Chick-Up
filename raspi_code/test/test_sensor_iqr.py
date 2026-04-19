"""
Path: test/test_sensor_iqr.py
Description:
    Standalone test for IQR-based average filter on both HC-SR04 sensors.

    Algorithm per reading:
        STEP 1 — Collect 50 raw _measure_once() samples into a list
        STEP 2 — Remove outliers using IQR (Interquartile Range):
                    Q1 = 25th percentile
                    Q3 = 75th percentile
                    IQR = Q3 - Q1
                    Keep only values inside [Q1 - 1.5×IQR, Q3 + 1.5×IQR]
        STEP 3 — Average the remaining clean values
        STEP 4 — That average is the final reading

    Output per cycle:
        - raw      : single _measure_once() reading (for comparison)
        - samples  : how many of the 50 survived the IQR filter
        - avg      : final IQR-averaged value

    Run from raspi_code/ root:
        sudo python test/test_sensor_iqr.py

    Stop with Ctrl+C.
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import RPi.GPIO as GPIO
from lib.services.hardware.ultrasonic_controller import (
    setup_ultrasonics,
    _measure_once,
    LEFT_TRIG, LEFT_ECHO,
    RIGHT_TRIG, RIGHT_ECHO,
)

# ─────────────────────────── CONFIG ──────────────────────────────────────────

SAMPLE_COUNT = 50
SAMPLE_DELAY = 0.01    # 10ms between samples — faster collection
VALID_MIN_CM = 2.0
VALID_MAX_CM = 400.0

# ─────────────────────────── IQR FILTER ──────────────────────────────────────

def _iqr_average(trig: int, echo: int) -> tuple:
    """
    Collect SAMPLE_COUNT readings, remove outliers via IQR, return average.

    Returns:
        tuple: (final_avg_cm, clean_sample_count, raw_single_cm)
            final_avg_cm      : IQR-filtered average in cm (0.0 if no clean samples)
            clean_sample_count: how many samples survived the IQR filter
            raw_single_cm     : one raw _measure_once reading for comparison
    """
    # ── STEP 1: Collect 50 samples ────────────────────────────────────────
    samples = []
    raw_single = _measure_once(trig, echo)   # one raw reading for comparison

    for _ in range(SAMPLE_COUNT):
        reading = _measure_once(trig, echo)
        if VALID_MIN_CM <= reading <= VALID_MAX_CM:
            samples.append(reading)
        time.sleep(SAMPLE_DELAY)

    if not samples:
        return 0.0, 0, raw_single

    if len(samples) < 4:
        # Not enough data for IQR — fall back to simple average
        return round(sum(samples) / len(samples), 2), len(samples), raw_single

    # ── STEP 2: IQR outlier removal ───────────────────────────────────────
    sorted_samples = sorted(samples)
    n   = len(sorted_samples)
    q1  = sorted_samples[n // 4]
    q3  = sorted_samples[(3 * n) // 4]
    iqr = q3 - q1

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    clean = [s for s in sorted_samples if lower_bound <= s <= upper_bound]

    if not clean:
        return 0.0, 0, raw_single

    # ── STEP 3 + 4: Average the clean values ─────────────────────────────
    final_avg = round(sum(clean) / len(clean), 2)
    return final_avg, len(clean), raw_single


# ─────────────────────────── MAIN ────────────────────────────────────────────

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    print("\nInitializing sensors...")
    setup_ultrasonics()
    print("Sensors ready.\n")

    print("=" * 66)
    print("  IQR Average Filter Test — Feed (Left) + Water (Right)")
    print(f"  Collecting {SAMPLE_COUNT} samples per reading")
    print("  raw     = single _measure_once reading")
    print("  samples = how many survived IQR filter")
    print("  avg     = final IQR-filtered average")
    print("  Ctrl+C to stop")
    print("=" * 66)

    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"\nCycle #{cycle}")
            print("-" * 66)

            # ── Feed sensor ───────────────────────────────────────────────
            feed_avg, feed_clean, feed_raw = _iqr_average(LEFT_TRIG, LEFT_ECHO)
            print(
                f"  FEED  (left)  | raw: {feed_raw:>8.2f} cm  | "
                f"samples: {feed_clean:>2}/{SAMPLE_COUNT}  | "
                f"avg: {feed_avg:>8.2f} cm"
            )

            # ── Water sensor ──────────────────────────────────────────────
            water_avg, water_clean, water_raw = _iqr_average(RIGHT_TRIG, RIGHT_ECHO)
            print(
                f"  WATER (right) | raw: {water_raw:>8.2f} cm  | "
                f"samples: {water_clean:>2}/{SAMPLE_COUNT}  | "
                f"avg: {water_avg:>8.2f} cm"
            )

            print("-" * 66)

    except KeyboardInterrupt:
        print("\n\nTest stopped by user.")

    finally:
        GPIO.cleanup()
        print("GPIO cleaned up.")


if __name__ == "__main__":
    main()