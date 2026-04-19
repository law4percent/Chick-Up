"""
Path: test/test_gpio_free_pins.py
Description:
    Scans all free BCM GPIO pins on Raspberry Pi 4B and reports
    which ones are healthy and which are broken/damaged.

    Skipped pins (already in use or reserved):
        2, 3   — I2C SDA/SCL (LCD at 0x27)
        4      — Keypad row
        7      — Water sensor TRIG
        8      — Water sensor ECHO
        12     — Keypad col
        16     — Keypad row
        17     — Feed motor relay
        18     — Keypad col
        20     — Keypad row
        21     — Keypad row
        23     — Keypad col
        24     — Feed sensor ECHO (currently broken)
        25     — Feed sensor TRIG
        26     — Keypad col
        27     — Water motor relay

    Free pins tested:
        5, 6, 9, 10, 11, 13, 14, 15, 19, 22

    Test method per pin:
        1. Setup as OUTPUT
        2. Set HIGH → read back → expect HIGH
        3. Set LOW  → read back → expect LOW
        4. Setup as INPUT with pull-down
        5. Read → expect LOW (floating pins pulled down)
        A pin PASSES if all 3 checks succeed.

    Run from raspi_code/ root:
        sudo python test/test_gpio_free_pins.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import RPi.GPIO as GPIO

# ─────────────────────────── PIN LISTS ───────────────────────────────────────

FREE_PINS = [5, 6, 9, 10, 11, 13, 14, 15, 19, 22]

# ─────────────────────────── TEST ────────────────────────────────────────────

def _test_pin(pin: int) -> dict:
    """
    Test a single GPIO pin for output and input health.

    Returns:
        dict with keys: pin, out_high, out_low, in_pulldown, healthy
    """
    result = {
        "pin"         : pin,
        "out_high"    : False,
        "out_low"     : False,
        "in_pulldown" : False,
        "healthy"     : False,
    }

    try:
        # ── Output test ───────────────────────────────────────────────────
        GPIO.setup(pin, GPIO.OUT)

        GPIO.output(pin, GPIO.HIGH)
        time.sleep(0.01)
        result["out_high"] = GPIO.input(pin) == GPIO.HIGH

        GPIO.output(pin, GPIO.LOW)
        time.sleep(0.01)
        result["out_low"] = GPIO.input(pin) == GPIO.LOW

        # ── Input test (pull-down) ────────────────────────────────────────
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        time.sleep(0.01)
        result["in_pulldown"] = GPIO.input(pin) == GPIO.LOW

        result["healthy"] = (
            result["out_high"] and
            result["out_low"]  and
            result["in_pulldown"]
        )

    except Exception as e:
        result["error"] = str(e)

    finally:
        # Always reset to input with pull-down after test
        try:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        except Exception:
            pass

    return result


# ─────────────────────────── MAIN ────────────────────────────────────────────

def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    print("\n" + "=" * 58)
    print("  Free GPIO Pin Health Check — Raspberry Pi 4B")
    print(f"  Testing pins: {FREE_PINS}")
    print("  Skipped: 2,3 (I2C) + all currently used project pins")
    print("=" * 58)

    results = []
    for pin in FREE_PINS:
        result = _test_pin(pin)
        results.append(result)

        status = "PASS ✓" if result["healthy"] else "FAIL ✗"
        out_h  = "✓" if result["out_high"]    else "✗"
        out_l  = "✓" if result["out_low"]     else "✗"
        in_pd  = "✓" if result["in_pulldown"] else "✗"
        print(
            f"  GPIO {pin:>2} | {status} | "
            f"OUT_HIGH: {out_h}  OUT_LOW: {out_l}  IN_PULLDOWN: {in_pd}"
        )
        time.sleep(0.05)

    # ── Summary ───────────────────────────────────────────────────────────
    healthy_pins = [r["pin"] for r in results if r["healthy"]]
    broken_pins  = [r["pin"] for r in results if not r["healthy"]]

    print("\n" + "=" * 58)
    print("  SUMMARY")
    print("=" * 58)
    print(f"  Healthy pins : {healthy_pins if healthy_pins else 'None'}")
    print(f"  Broken pins  : {broken_pins  if broken_pins  else 'None'}")
    print("=" * 58)

    if healthy_pins:
        print(f"\n  ✓ Recommended pins for new ECHO assignment: {healthy_pins}")
        print("    Pick any pin from the healthy list above.")
    else:
        print("\n  ✗ No healthy free pins found — check Pi hardware.")
    print()

    GPIO.cleanup()


if __name__ == "__main__":
    main()