"""
Path: test/test_sensor.py
Description:
    Standalone test script for HC-SR04 ultrasonic sensors.
    Tests both feed (left) and water (right) sensors one after the other.
    Prints raw cm distance from both _measure_once and _median_distance
    so you can compare stability side by side.

    Run from raspi_code/ root:
        sudo python test/test_sensor.py

    Stop with Ctrl+C.
"""

import sys
import os
import time
import statistics

# ── Allow imports from raspi_code/ root ──────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import RPi.GPIO as GPIO
from lib.services.hardware.ultrasonic_controller import (
    setup_ultrasonics,
    _measure_once,
    _median_distance,
    LEFT_TRIG, LEFT_ECHO,
    RIGHT_TRIG, RIGHT_ECHO,
    SAMPLE_COUNT,
)

# ─────────────────────────── CONFIG ──────────────────────────────────────────

LOOP_DELAY = 0.5   # seconds between each full read cycle

# ─────────────────────────── HELPERS ─────────────────────────────────────────

def _divider():
    print("-" * 52)

def _header():
    print("=" * 52)
    print("  HC-SR04 Sensor Test — Feed (Left) + Water (Right)")
    print("  raw   = single _measure_once reading")
    print(f"  median = median of {SAMPLE_COUNT} samples (_median_distance)")
    print("  Ctrl+C to stop")
    print("=" * 52)

# ─────────────────────────── MAIN ────────────────────────────────────────────

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    print("\nInitializing sensors...")
    setup_ultrasonics()
    print("Sensors ready.\n")

    _header()

    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"\nCycle #{cycle}")
            _divider()

            # ── Feed sensor (left) ────────────────────────────────────────
            feed_raw    = _measure_once(LEFT_TRIG, LEFT_ECHO)
            feed_median = _median_distance(LEFT_TRIG, LEFT_ECHO)
            print(f"  FEED  (left)  | raw: {feed_raw:>8.2f} cm  | median: {feed_median:>8.2f} cm")

            # ── Water sensor (right) ──────────────────────────────────────
            water_raw    = _measure_once(RIGHT_TRIG, RIGHT_ECHO)
            water_median = _median_distance(RIGHT_TRIG, RIGHT_ECHO)
            print(f"  WATER (right) | raw: {water_raw:>8.2f} cm  | median: {water_median:>8.2f} cm")

            _divider()
            time.sleep(LOOP_DELAY)

    except KeyboardInterrupt:
        print("\n\nTest stopped by user.")

    finally:
        GPIO.cleanup()
        print("GPIO cleaned up.")


if __name__ == "__main__":
    main()