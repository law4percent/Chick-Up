"""
Keypad 4x4 Module
Provides a class-based interface for reading input from a 4x4 matrix keypad.

Loc: lib/services/hardware/keypad_controller.py
"""

import RPi.GPIO as GPIO
import time
from typing import Optional, List, Callable


class KeypadError(Exception):
    """Base exception for keypad errors"""
    pass


class Keypad4x4:
    """
    Interface for 4x4 matrix keypad using GPIO.

    Default Layout:
        [1] [2] [3] [A]
        [4] [5] [6] [B]
        [7] [8] [9] [C]
        [*] [0] [#] [D]

    Example usage:
        keypad = Keypad4x4()

        # Single key read
        key = keypad.read_key()
        if key:
            print(f"Pressed: {key}")

        # Wait for specific key
        key = keypad.wait_for_key(valid_keys=['1', '2', '3'])

        # Read multi-character input (terminated by '#')
        code = keypad.read_input(length=4)

        # Read numeric-only input
        pin = keypad.read_numeric(length=4)

        # Confirm action (# = yes, * = no)
        confirmed = keypad.confirm_action()
    """

    # Default GPIO pin configuration (BCM numbering)
    DEFAULT_ROW_PINS = [19, 21, 20, 16]
    DEFAULT_COL_PINS = [12, 23, 6, 22]   # 23 and 22 replace dead GPIO 13 and GPIO 5

    # Default key matrix layout
    DEFAULT_MATRIX = [
        ['1', '2', '3', 'A'],
        ['4', '5', '6', 'B'],
        ['7', '8', '9', 'C'],
        ['*', '0', '#', 'D']
    ]

    def __init__(
        self,
        row_pins        : List[int] = None,
        col_pins        : List[int] = None,
        matrix          : List[List[str]] = None,
        debounce_time   : float = 0.05,
        stability_delay : float = 0.002
    ):
        self.row_pins        = row_pins or self.DEFAULT_ROW_PINS
        self.col_pins        = col_pins or self.DEFAULT_COL_PINS
        self.matrix          = matrix or self.DEFAULT_MATRIX
        self.debounce_time   = debounce_time
        self.stability_delay = stability_delay

        self._is_setup      = False
        self._last_key      = None
        self._last_key_time = 0

        self._validate_configuration()
        self.setup()

    # ─────────────────────────── SETUP ───────────────────────────────────

    def _validate_configuration(self) -> None:
        """Validate pin configuration and matrix layout"""
        if len(self.row_pins) != 4:
            raise KeypadError("Exactly 4 row pins required")
        if len(self.col_pins) != 4:
            raise KeypadError("Exactly 4 column pins required")
        if len(self.matrix) != 4 or any(len(row) != 4 for row in self.matrix):
            raise KeypadError("Matrix must be 4x4 (4 rows, 4 columns)")

    def setup(self) -> None:
        """
        Initialize GPIO pins for the keypad.

        FIX: Always force a clean re-init regardless of _is_setup state.
        When systemd stops the service, GPIO.cleanup() wipes all pin modes.
        On the next start, _is_setup would still be True on the object but
        the GPIO hardware state is gone — skipping setup causes floating pins.
        """
        if self._is_setup:
            # Force reset pins before re-initializing — clears any dirty state
            # left over from a previous run that didn't call cleanup() cleanly.
            try:
                for pin in self.row_pins:
                    GPIO.output(pin, GPIO.HIGH)
            except Exception:
                pass  # pins may already be unconfigured — that's fine, we re-setup below
            self._is_setup = False

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            for pin in self.row_pins:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)

            for pin in self.col_pins:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            self._is_setup = True

        except Exception as e:
            raise KeypadError(f"Failed to setup GPIO: {e}")

    # ─────────────────────────── SCAN ────────────────────────────────────

    def scan_key(self) -> Optional[str]:
        """
        Scan keypad once and return pressed key.

        Returns:
            str: Key character if pressed, None otherwise
        """
        if not self._is_setup:
            raise KeypadError("Keypad not setup. Call setup() first.")

        for i, row_pin in enumerate(self.row_pins):
            GPIO.output(row_pin, GPIO.LOW)
            time.sleep(self.stability_delay)

            for j, col_pin in enumerate(self.col_pins):
                if GPIO.input(col_pin) == GPIO.LOW:
                    GPIO.output(row_pin, GPIO.HIGH)
                    return self.matrix[i][j]

            GPIO.output(row_pin, GPIO.HIGH)

        return None

    def read_key(self, with_debounce: bool = True) -> Optional[str]:
        """
        Read a single key press with optional debouncing.

        Args:
            with_debounce: Apply debounce delay to prevent multiple reads

        Returns:
            str: Pressed key or None
        """
        key = self.scan_key()

        if key and with_debounce:
            current_time = time.time()
            if key == self._last_key and (current_time - self._last_key_time) < self.debounce_time:
                return None

            self._last_key      = key
            self._last_key_time = current_time

            # Wait for key release
            while self.scan_key() is not None:
                time.sleep(0.01)

        return key

    # ─────────────────────────── WAIT / INPUT ────────────────────────────

    def wait_for_key(
        self,
        valid_keys : Optional[List[str]] = None,
        timeout    : Optional[float]     = None
    ) -> Optional[str]:
        """
        Block until a key is pressed.

        Args:
            valid_keys: List of acceptable keys. If None, accepts any key.
            timeout:    Maximum time to wait in seconds. None = wait forever.

        Returns:
            str: Pressed key, or None if timeout
        """
        start_time = time.time()

        while True:
            if timeout and (time.time() - start_time) > timeout:
                return None

            key = self.read_key()

            if key:
                if valid_keys is None or key in valid_keys:
                    return key

            time.sleep(0.05)

    def read_input(
        self,
        length        : int                          = None,
        valid_keys    : Optional[List[str]]          = None,
        end_key       : str                          = '#',
        cancel_key    : str                          = '*',
        echo_callback : Optional[Callable[[str], None]] = None,
        timeout       : Optional[float]              = None
    ) -> Optional[str]:
        """
        Read multi-character input from keypad.

        Args:
            length:        Maximum input length. None = unlimited until end_key.
            valid_keys:    Acceptable keys (excluding end_key, cancel_key)
            end_key:       Key to confirm input (default: '#')
            cancel_key:    Key to cancel input (default: '*')
            echo_callback: Function called with current buffer on each key press
            timeout:       Maximum time to wait in seconds

        Returns:
            str: Input string, or None if cancelled/timeout

        Example:
            # Read 4-digit PIN
            pin = keypad.read_input(
                length=4,
                valid_keys=['0','1','2','3','4','5','6','7','8','9'],
                echo_callback=lambda s: print(f"PIN: {'*' * len(s)}")
            )
        """
        input_buffer = ""
        start_time   = time.time()

        while True:
            if timeout and (time.time() - start_time) > timeout:
                return None

            key = self.read_key()

            if key:
                if key == cancel_key:
                    return None

                if key == end_key:
                    return input_buffer if input_buffer else None

                if valid_keys and key not in valid_keys:
                    continue

                if length and len(input_buffer) >= length:
                    return input_buffer

                input_buffer += key

                if echo_callback:
                    echo_callback(input_buffer)

            time.sleep(0.05)

    def read_numeric(
        self,
        length        : int,
        echo_callback : Optional[Callable[[str], None]] = None,
        timeout       : Optional[float]                 = None
    ) -> Optional[str]:
        """
        Read numeric input only (0-9).

        Args:
            length:        Exact number of digits required
            echo_callback: Function called with current buffer on each digit
            timeout:       Maximum time to wait

        Returns:
            str: Numeric string or None
        """
        valid_keys = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
        return self.read_input(
            length        = length,
            valid_keys    = valid_keys,
            echo_callback = echo_callback,
            timeout       = timeout
        )

    def confirm_action(
        self,
        confirm_key : str             = '#',
        cancel_key  : str             = '*',
        timeout     : Optional[float] = None
    ) -> bool:
        """
        Wait for user confirmation.

        Args:
            confirm_key: Key for yes/confirm (default: '#')
            cancel_key:  Key for no/cancel (default: '*')
            timeout:     Maximum time to wait

        Returns:
            bool: True if confirmed, False if cancelled/timeout
        """
        key = self.wait_for_key(
            valid_keys=[confirm_key, cancel_key],
            timeout=timeout
        )
        return key == confirm_key

    # ─────────────────────────── MATRIX UTILS ────────────────────────────

    def get_matrix(self) -> List[List[str]]:
        """Get current key matrix layout"""
        return self.matrix

    def set_matrix(self, matrix: List[List[str]]) -> None:
        """
        Set custom key matrix layout.

        Args:
            matrix: 4x4 matrix of key characters
        """
        if len(matrix) != 4 or any(len(row) != 4 for row in matrix):
            raise KeypadError("Matrix must be 4x4")
        self.matrix = matrix

    # ─────────────────────────── CLEANUP ─────────────────────────────────

    def cleanup(self) -> None:
        """
        Cleanup keypad GPIO pins only.

        FIX: Use GPIO.cleanup(pins) instead of GPIO.cleanup() to avoid
        wiping pins owned by motor_controller and ultrasonic_controller.
        GPIO.cleanup() with no args resets ALL pins — this was silently
        breaking other modules on service restart.
        """
        if self._is_setup:
            all_pins = self.row_pins + self.col_pins
            GPIO.cleanup(all_pins)   # only release keypad pins
            self._is_setup = False

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __repr__(self) -> str:
        return f"Keypad4x4(rows={self.row_pins}, cols={self.col_pins})"


# ===== USAGE EXAMPLES =====

if __name__ == "__main__":
    import sys

    print("=== Keypad4x4 Test ===")
    print("Default pins — Row: [19,21,20,16]  Col: [12,13,6,5]")
    print()

    keypad = Keypad4x4()

    # ── Test 1: Single key read (press any key) ──────────────────────────
    print("[Test 1] Single key read — press any key...")
    key = keypad.wait_for_key(timeout=10)
    print(f"  Got: {key}")
    print()

    # ── Test 2: Wait for specific keys ───────────────────────────────────
    print("[Test 2] Wait for A, B, C, or D...")
    key = keypad.wait_for_key(valid_keys=['A', 'B', 'C', 'D'], timeout=10)
    print(f"  Got: {key}")
    print()

    # ── Test 3: Numeric PIN entry (4 digits, auto-confirm on length) ─────
    print("[Test 3] Enter 4-digit PIN (auto-confirms after 4 digits)...")
    pin = keypad.read_numeric(
        length=4,
        echo_callback=lambda s: print(f"  Buffer: {'*' * len(s)}", end='\r')
    )
    print(f"\n  PIN entered: {pin}")
    print()

    # ── Test 4: Free input with # to confirm, * to cancel ────────────────
    print("[Test 4] Type anything, press # to confirm or * to cancel...")
    result = keypad.read_input(
        echo_callback=lambda s: print(f"  Input: {s}", end='\r'),
        timeout=30
    )
    print(f"\n  Result: {result}")
    print()

    # ── Test 5: Confirm action ────────────────────────────────────────────
    print("[Test 5] Confirm action — press # (yes) or * (no)...")
    confirmed = keypad.confirm_action(timeout=10)
    print(f"  Confirmed: {confirmed}")
    print()

    keypad.cleanup()
    print("=== Done ===")