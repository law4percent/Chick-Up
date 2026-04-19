"""
Path: test/test_gpio_sensors.py
Description:
    GPIO pin health check for HC-SR04 sensor pins only.

    Tests:
        Feed  (left)  — TRIG 25 (OUT), ECHO 24 (IN)
        Water (right) — TRIG 7  (OUT), ECHO 8  (IN)

    What it checks:
        TRIG pins (OUT):
            - Set HIGH → read back HIGH → confirm pin is driveable
            - Set LOW  → read back LOW  → confirm pin resets cleanly

        ECHO pins (IN):
            - Fire a real TRIG pulse → wait for ECHO to go HIGH
            - If ECHO goes HIGH within timeout → pin is receiving signal
            - If ECHO never goes HIGH → wiring fault or sensor dead

    Run from raspi_code/ root:
        sudo python test/test_gpio_sensors.py

    Stop with Ctrl+C.
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import RPi.GPIO as GPIO

# ─────────────────────────── PIN DEFINITIONS ─────────────────────────────────

PINS = {
    "feed": {
        "trig": 25,
        "echo": 24,
    },
    "water": {
        "trig": 7,
        "echo": 8,
    },
}

ECHO_TIMEOUT = 0.04   # 40ms — same as ultrasonic_controller

# ─────────────────────────── HELPERS ─────────────────────────────────────────

def _divider():
    print("-" * 52)

def _test_trig(label: str, trig_pin: int) -> bool:
    """
    Drive TRIG pin HIGH then LOW and read back.
    Returns True if pin responds correctly.
    """
    print(f"\n  [{label}] TRIG pin {trig_pin} (OUT)")

    # Set HIGH
    GPIO.output(trig_pin, True)
    time.sleep(0.01)
    state_high = GPIO.input(trig_pin)
    result_high = state_high == GPIO.HIGH
    print(f"    Set HIGH → read back: {'HIGH ✓' if result_high else 'LOW  ✗ (pin not responding)'}")

    # Set LOW
    GPIO.output(trig_pin, False)
    time.sleep(0.01)
    state_low = GPIO.input(trig_pin)
    result_low = state_low == GPIO.LOW
    print(f"    Set LOW  → read back: {'LOW  ✓' if result_low else 'HIGH ✗ (pin stuck HIGH)'}")

    return result_high and result_low


def _test_echo(label: str, trig_pin: int, echo_pin: int) -> bool:
    """
    Fire a real TRIG pulse and check if ECHO pin responds.
    Returns True if ECHO goes HIGH within timeout.
    """
    print(f"\n  [{label}] ECHO pin {echo_pin} (IN) — firing pulse on TRIG {trig_pin}")

    # Fire 10µs trigger pulse
    GPIO.output(trig_pin, True)
    time.sleep(0.00001)
    GPIO.output(trig_pin, False)

    # Wait for ECHO to go HIGH
    timeout = time.time() + ECHO_TIMEOUT
    echo_received = False
    while time.time() < timeout:
        if GPIO.input(echo_pin) == GPIO.HIGH:
            echo_received = True
            break

    if echo_received:
        print(f"    ECHO went HIGH ✓ — pin is receiving signal")
    else:
        print(f"    ECHO never went HIGH ✗ — wiring fault or sensor dead")

    return echo_received


# ─────────────────────────── MAIN ────────────────────────────────────────────

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Setup pins
    for sensor, pins in PINS.items():
        GPIO.setup(pins["trig"], GPIO.OUT)
        GPIO.setup(pins["echo"], GPIO.IN)
        GPIO.output(pins["trig"], False)

    # Settle time
    time.sleep(0.5)

    print("\n" + "=" * 52)
    print("  GPIO Pin Health Check — Sensor Pins")
    print("  Feed  (left)  : TRIG 25, ECHO 24")
    print("  Water (right) : TRIG 7,  ECHO 8")
    print("=" * 52)

    results = {}

    for sensor, pins in PINS.items():
        label = sensor.upper()
        _divider()
        print(f"  Sensor: {label}")

        trig_ok = _test_trig(label, pins["trig"])
        time.sleep(0.1)
        echo_ok = _test_echo(label, pins["trig"], pins["echo"])

        results[sensor] = {
            "trig": trig_ok,
            "echo": echo_ok,
        }
        time.sleep(0.3)

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 52)
    print("  SUMMARY")
    print("=" * 52)
    for sensor, res in results.items():
        trig_status = "OK  ✓" if res["trig"] else "FAIL ✗"
        echo_status = "OK  ✓" if res["echo"] else "FAIL ✗"
        print(f"  {sensor.upper():<6} | TRIG: {trig_status}  | ECHO: {echo_status}")

    print("=" * 52)

    all_ok = all(v for res in results.values() for v in res.values())
    if all_ok:
        print("  All pins OK — wiring looks good.")
    else:
        print("  One or more pins FAILED — check wiring or sensor.")
    print()

    GPIO.cleanup()


if __name__ == "__main__":
    main()