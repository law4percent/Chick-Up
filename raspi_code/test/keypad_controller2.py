"""
Keypad 4x4 — Pin Debugger
Verifies GPIO wiring by scanning each row/col pin independently.
Prints a live readout so you can confirm physical presses.

Loc: lib/services/hardware/keypad_pin_debugger.py

Usage:
    python keypad_pin_debugger.py                  # full interactive debug
    python keypad_pin_debugger.py --raw            # raw GPIO level dump only
    python keypad_pin_debugger.py --scan           # single scan snapshot
    python keypad_pin_debugger.py --pin 19         # watch one GPIO pin
"""

import RPi.GPIO as GPIO
import time
import argparse
import sys
from typing import List, Optional


# ── Pin config (mirrors Keypad4x4 defaults) ──────────────────────────────────

ROW_PINS = [19, 21, 20, 16]   # OUTPUT — driven LOW one row at a time
COL_PINS = [12, 13,  6,  5]   # INPUT  — read LOW when key is pressed

MATRIX = [
    ['1', '2', '3', 'A'],
    ['4', '5', '6', 'B'],
    ['7', '8', '9', 'C'],
    ['*', '0', '#', 'D'],
]

STABILITY_DELAY = 0.002   # seconds between row drive and column read
POLL_INTERVAL   = 0.05    # seconds between full scans in live mode


# ── GPIO helpers ─────────────────────────────────────────────────────────────

def setup_gpio() -> None:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in ROW_PINS:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)          # idle HIGH
    for pin in COL_PINS:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)


def teardown_gpio() -> None:
    GPIO.cleanup()


# ── Raw level dump ────────────────────────────────────────────────────────────

def dump_raw_levels() -> None:
    """
    Print the current GPIO level of every row and col pin without
    activating any row drive. Useful for checking pull-up wiring.
    """
    print("\n── Raw GPIO levels (no row driven) ─────────────────────────")
    print(f"  {'PIN':<8} {'ROLE':<12} {'LEVEL'}")
    print(f"  {'---':<8} {'----':<12} {'-----'}")

    # Read row pins as inputs momentarily
    for i, pin in enumerate(ROW_PINS):
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        lvl = GPIO.input(pin)
        label = "HIGH (idle)" if lvl == GPIO.HIGH else "LOW  (!)"
        print(f"  GPIO {pin:<4} Row {i} (OUT)  {label}")
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)          # restore to output HIGH

    for j, pin in enumerate(COL_PINS):
        lvl = GPIO.input(pin)
        label = "HIGH (idle)" if lvl == GPIO.HIGH else "LOW  (pressed?)"
        print(f"  GPIO {pin:<4} Col {j} (IN)   {label}")

    print()


# ── Single scan snapshot ──────────────────────────────────────────────────────

def scan_once() -> Optional[str]:
    """
    Run one full matrix scan. Returns the first key detected or None.
    Also prints a visual grid showing which intersections are LOW.
    """
    hit_row : Optional[int] = None
    hit_col : Optional[int] = None

    # Build a 4×4 grid of LOW/HIGH readings
    grid = [['·'] * 4 for _ in range(4)]

    for i, row_pin in enumerate(ROW_PINS):
        GPIO.output(row_pin, GPIO.LOW)
        time.sleep(STABILITY_DELAY)

        for j, col_pin in enumerate(COL_PINS):
            if GPIO.input(col_pin) == GPIO.LOW:
                grid[i][j] = 'X'
                if hit_row is None:       # record first hit
                    hit_row, hit_col = i, j

        GPIO.output(row_pin, GPIO.HIGH)

    # Print the grid
    print("\n── Scan grid (X = LOW detected) ─────────────────────────────")
    col_header = "       " + "  ".join(f"C{j}(G{COL_PINS[j]})" for j in range(4))
    print(col_header)
    for i in range(4):
        row_tag = f"R{i}(G{ROW_PINS[i]})"
        cells   = "   ".join(grid[i])
        print(f"  {row_tag:<12}  {cells}")

    if hit_row is not None:
        key = MATRIX[hit_row][hit_col]
        print(f"\n  ✓ Key detected: [{key}]  →  Row {hit_row} (GPIO {ROW_PINS[hit_row]}) "
              f"× Col {hit_col} (GPIO {COL_PINS[hit_col]})")
        return key
    else:
        print("\n  — No key pressed")
        return None


# ── Single-pin watcher ────────────────────────────────────────────────────────

def watch_pin(pin: int, duration: float = 15.0) -> None:
    """
    Monitor a single GPIO pin and print every level change.
    Useful for checking whether a specific pin is floating or stuck.
    """
    if pin not in ROW_PINS + COL_PINS:
        print(f"  [warn] GPIO {pin} is not in the keypad pin list — "
              f"rows={ROW_PINS}, cols={COL_PINS}")

    # Drive all rows HIGH so columns can be read cleanly
    for rp in ROW_PINS:
        GPIO.setup(rp, GPIO.OUT)
        GPIO.output(rp, GPIO.HIGH)

    if pin in ROW_PINS:
        role = f"Row {ROW_PINS.index(pin)} (OUTPUT mode)"
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)   # peek as input
    else:
        role = f"Col {COL_PINS.index(pin)} (INPUT mode)"

    print(f"\n── Watching GPIO {pin} [{role}] for {duration:.0f}s ──────────────────")
    print("  Press Ctrl-C to stop early\n")

    last_level = None
    deadline   = time.time() + duration

    try:
        while time.time() < deadline:
            lvl = GPIO.input(pin)
            if lvl != last_level:
                ts    = time.strftime("%H:%M:%S")
                state = "HIGH" if lvl == GPIO.HIGH else "LOW "
                event = "(idle / released)" if lvl == GPIO.HIGH else "(active / pressed)"
                print(f"  {ts}  GPIO {pin}  →  {state}  {event}")
                last_level = lvl
            time.sleep(0.005)

    except KeyboardInterrupt:
        print("\n  Stopped.")

    finally:
        # Restore row pin to output if we temporarily switched it
        if pin in ROW_PINS:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)


# ── Interactive live debug ────────────────────────────────────────────────────

def live_debug(duration: float = 30.0) -> None:
    """
    Continuously scan the matrix and print any key press with full
    pin diagnostics. Shows consecutive presses and hold detection.
    """
    print(f"\n── Live keypad debug — scanning for {duration:.0f}s ─────────────────")
    print("  Press keys on the keypad. Ctrl-C to stop early.\n")

    _COLS = "  ".join(f"G{p:>2}" for p in COL_PINS)
    print(f"  {'':12}  {_COLS}")
    print(f"  {'':12}  {'—————  ' * 4}")

    deadline    = time.time() + duration
    last_key    = None
    hold_start  = None
    press_count = 0

    try:
        while time.time() < deadline:
            # Build row readings
            row_results = []
            detected_key = None

            for i, row_pin in enumerate(ROW_PINS):
                GPIO.output(row_pin, GPIO.LOW)
                time.sleep(STABILITY_DELAY)

                cols_low = []
                for j, col_pin in enumerate(COL_PINS):
                    if GPIO.input(col_pin) == GPIO.LOW:
                        cols_low.append(j)
                        if detected_key is None:
                            detected_key = MATRIX[i][j]

                row_results.append((i, row_pin, cols_low))
                GPIO.output(row_pin, GPIO.HIGH)

            # Compact row/col line
            for i, row_pin, cols_low in row_results:
                if cols_low:
                    cells = "  ".join(
                        f"{'[X]' if j in cols_low else ' · '}" for j in range(4)
                    )
                    print(f"  R{i} G{row_pin:<3}         {cells}")

            # Key event reporting
            if detected_key:
                if detected_key != last_key:
                    press_count += 1
                    ts = time.strftime("%H:%M:%S.") + f"{int(time.time() * 1000) % 1000:03d}"
                    print(f"\n  [{ts}]  ↓ PRESS #{press_count}  key=[{detected_key}]")
                    last_key   = detected_key
                    hold_start = time.time()
                else:
                    hold_ms = int((time.time() - hold_start) * 1000)
                    print(f"  … holding [{detected_key}]  {hold_ms}ms", end='\r')
            else:
                if last_key:
                    hold_ms = int((time.time() - hold_start) * 1000)
                    ts = time.strftime("%H:%M:%S.") + f"{int(time.time() * 1000) % 1000:03d}"
                    print(f"\n  [{ts}]  ↑ RELEASE  key=[{last_key}]  held {hold_ms}ms\n")
                    last_key   = None
                    hold_start = None

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n  Stopped.")

    print(f"\n  Total presses detected: {press_count}")


# ── Pin continuity check ──────────────────────────────────────────────────────

def continuity_check() -> None:
    """
    Walks through each row pin, drives it LOW, and reads all columns.
    Confirms that at least one column can 'see' each row being driven.
    Helps detect open circuits or miswired pins.
    """
    print("\n── Continuity check ─────────────────────────────────────────")
    print("  Driving each row LOW and reading columns.\n")
    print("  NOTE: This is passive — you do NOT need to press any key.\n")

    all_ok = True

    for i, row_pin in enumerate(ROW_PINS):
        GPIO.output(row_pin, GPIO.LOW)
        time.sleep(STABILITY_DELAY)

        col_levels = {col_pin: GPIO.input(col_pin) for col_pin in COL_PINS}
        GPIO.output(row_pin, GPIO.HIGH)

        # All cols should remain HIGH when no key is pressed
        lows = [pin for pin, lvl in col_levels.items() if lvl == GPIO.LOW]
        status = "OK  — all cols HIGH (no ghost)" if not lows else f"WARN — unexpected LOW on {lows}"
        if lows:
            all_ok = False
        print(f"  Row {i}  GPIO {row_pin:<3}  →  {status}")

    print()
    if all_ok:
        print("  ✓ No unexpected LOW readings. Wiring looks clean.")
    else:
        print("  ✗ Unexpected LOW(s) detected. Check for shorts or floating pins.")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Keypad 4×4 GPIO pin debugger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
modes:
  (default)    interactive live scan for 30s
  --raw        dump raw GPIO levels and exit
  --scan       one-shot matrix scan and exit
  --continuity walk each row and check for shorts/opens
  --pin GPIO#  watch a single pin for 15s
  --duration N override scan/watch duration (seconds)
        """
    )
    parser.add_argument("--raw",         action="store_true", help="raw level dump")
    parser.add_argument("--scan",        action="store_true", help="single scan snapshot")
    parser.add_argument("--continuity",  action="store_true", help="continuity check")
    parser.add_argument("--pin",         type=int,            help="watch single GPIO pin")
    parser.add_argument("--duration",    type=float, default=30.0,
                                         help="live/watch duration in seconds (default: 30)")
    args = parser.parse_args()

    print("═══════════════════════════════════════════════")
    print("  Keypad 4×4 — GPIO Pin Debugger")
    print(f"  Rows (OUT): {ROW_PINS}")
    print(f"  Cols (IN):  {COL_PINS}")
    print("═══════════════════════════════════════════════")

    try:
        setup_gpio()

        if args.raw:
            dump_raw_levels()
        elif args.scan:
            scan_once()
        elif args.continuity:
            continuity_check()
        elif args.pin is not None:
            watch_pin(args.pin, duration=args.duration)
        else:
            # Default: full diagnostic then live debug
            dump_raw_levels()
            continuity_check()
            live_debug(duration=args.duration)

    except Exception as e:
        print(f"\n  [ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    finally:
        teardown_gpio()
        print("GPIO cleaned up.")


if __name__ == "__main__":
    main()