"""
Path: test/test_sensor_water.py
Description:
    Standalone test script for the water (right) HC-SR04 sensor only.
    Prints raw cm distance from both _measure_once and _median_distance
    so you can compare stability side by side.

    Run from raspi_code/ root:
        sudo python test/test_sensor_water.py

    Stop with Ctrl+C.
"""

import sys
import os
import time

# ── Allow imports from raspi_code/ root ──────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import RPi.GPIO as GPIO
from lib.services.hardware.ultrasonic_controller import (
    setup_ultrasonics,
    _measure_once,
    _median_distance,
    RIGHT_TRIG, RIGHT_ECHO,
    SAMPLE_COUNT,
)

# ─────────────────────────── CONFIG ──────────────────────────────────────────

LOOP_DELAY = 0.5   # seconds between each read cycle

# ─────────────────────────── MAIN ────────────────────────────────────────────

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    print("\nInitializing water sensor (right — TRIG 7, ECHO 8)...")
    setup_ultrasonics()
    print("Sensor ready.\n")

    print("=" * 52)
    print("  HC-SR04 Water Sensor Test (Right)")
    print(f"  raw    = single _measure_once reading")
    print(f"  median = median of {SAMPLE_COUNT} samples (_median_distance)")
    print("  Ctrl+C to stop")
    print("=" * 52)

    cycle = 0
    try:
        while True:
            cycle += 1
            raw    = _measure_once(RIGHT_TRIG, RIGHT_ECHO)
            median = _median_distance(RIGHT_TRIG, RIGHT_ECHO)
            print(f"  Cycle #{cycle:>4d} | raw: {raw:>8.2f} cm  | median: {median:>8.2f} cm")
            time.sleep(LOOP_DELAY)

    except KeyboardInterrupt:
        print("\n\nTest stopped by user.")

    finally:
        GPIO.cleanup()
        print("GPIO cleaned up.")


if __name__ == "__main__":
    main()