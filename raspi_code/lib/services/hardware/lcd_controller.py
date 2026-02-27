"""
LCD Controller for I2C LCD Display
Loc: lib/services/hardware/lcd_controller.py

Supports 16x2 and 20x4 character LCD displays with PCF8574 I2C backpack.
Uses the OLD (tested) low-level I2C/init logic combined with the NEW class-based API.
"""

import smbus2
import time
from typing import List, Optional, Tuple, Callable
from enum import Enum

# ─────────────────────────── ENUMS ───────────────────────────────────────────

class LCDSize(Enum):
    """Standard LCD sizes"""
    LCD_16x2 = (16, 2)
    LCD_20x4 = (20, 4)


# ─────────────────────────── EXCEPTIONS ──────────────────────────────────────

class LCDError(Exception):
    """Base exception for LCD errors"""
    pass


class LCDConnectionError(LCDError):
    """Raised when LCD connection fails"""
    pass


# ─────────────────────────── MAIN CLASS ──────────────────────────────────────

class LCD_I2C:
    """
    I2C LCD Display Controller for PCF8574 backpack.
    Supports 16x2 and 20x4 character LCD displays.

    Low-level init sequence from the OLD tested code (HD44780 datasheet).
    High-level API from the NEW class-based design.

    Example usage:
        lcd = LCD_I2C(address=0x27, size=LCDSize.LCD_20x4)

        # Simple text
        lcd.show("Hello, World!")

        # Multi-line
        lcd.show(["Line 1", "Line 2", "Line 3"])

        # Temporary message (auto-clears after 2s)
        lcd.show("Please wait...", duration=2)

        # Write at specific position
        lcd.write_at(0, 0, "Top Left")

        # Scrollable list
        lcd.show_scrollable(["Item 1", "Item 2", "Item 3", "Item 4", "Item 5"])

        # Scrollable menu with cursor
        choice = lcd.show_scrollable_menu(
            title="SELECT MODE",
            options=["[1] Option A", "[2] Option B", "[3] Option C"],
            keypad=kp
        )
    """

    # LCD Commands
    LCD_CLEARDISPLAY   = 0x01
    LCD_RETURNHOME     = 0x02
    LCD_ENTRYMODESET   = 0x04
    LCD_DISPLAYCONTROL = 0x08
    LCD_CURSORSHIFT    = 0x10
    LCD_FUNCTIONSET    = 0x20
    LCD_SETCGRAMADDR   = 0x40
    LCD_SETDDRAMADDR   = 0x80

    # Entry mode flags
    LCD_ENTRYLEFT           = 0x02
    LCD_ENTRYSHIFTDECREMENT = 0x00

    # Display control flags
    LCD_DISPLAYON  = 0x04
    LCD_DISPLAYOFF = 0x00
    LCD_CURSORON   = 0x02
    LCD_CURSOROFF  = 0x00
    LCD_BLINKON    = 0x01
    LCD_BLINKOFF   = 0x00

    # Cursor/display shift flags
    LCD_DISPLAYMOVE = 0x08
    LCD_MOVERIGHT   = 0x04
    LCD_MOVELEFT    = 0x00

    # Function set flags
    LCD_4BITMODE = 0x00
    LCD_2LINE    = 0x08
    LCD_5x8DOTS  = 0x00

    # Backlight
    LCD_BACKLIGHT   = 0x08
    LCD_NOBACKLIGHT = 0x00

    # PCF8574 bit positions
    En = 0x04   # Enable bit
    Rs = 0x01   # Register select bit

    def __init__(
        self,
        address   : int     = 0x27,
        bus       : int     = 1,
        size      : LCDSize = LCDSize.LCD_20x4,
        backlight : bool    = True
    ):
        """
        Initialize LCD display.

        Args:
            address:   I2C address (usually 0x27 or 0x3F)
            bus:       I2C bus number (1 for Raspberry Pi)
            size:      LCD size enum (LCDSize.LCD_16x2 or LCDSize.LCD_20x4)
            backlight: Enable backlight on startup
        """
        self.address         = address
        self.bus_number      = bus
        self.cols, self.rows = size.value
        self.backlight_state = self.LCD_BACKLIGHT if backlight else self.LCD_NOBACKLIGHT

        # Row address offsets (HD44780 standard)
        self.row_offsets = [0x00, 0x40, 0x14, 0x54]

        try:
            self.bus = smbus2.SMBus(self.bus_number)
        except Exception as e:
            raise LCDConnectionError(f"Failed to open I2C bus {bus}: {e}")

        self._initialize()

    # ─────────────────────────── LOW-LEVEL I2C (from OLD tested code) ────────

    def _i2c_write(self, data: int) -> None:
        """Write a single byte to the I2C bus."""
        self.bus.write_byte(self.address, data | self.backlight_state)

    def _pulse_enable(self, data: int) -> None:
        """Pulse the EN pin high then low to latch the nibble."""
        self._i2c_write(data | self.En)
        time.sleep(0.0005)
        self._i2c_write(data & ~self.En)
        time.sleep(0.0005)

    def _send_nibble(self, nibble: int) -> None:
        """Send a single nibble (must already be in the upper 4 bits)."""
        self._i2c_write(nibble)
        self._pulse_enable(nibble)

    def _send_byte(self, data: int, mode: int) -> None:
        """
        Send a full byte in 4-bit mode: high nibble first, then low nibble.

        Args:
            data: Byte value (0x00–0xFF)
            mode: 0 for command, Rs for character data
        """
        self._send_nibble(mode | (data & 0xF0))           # high nibble
        self._send_nibble(mode | ((data & 0x0F) << 4))    # low nibble shifted up
        time.sleep(0.0005)

    def _send_command(self, cmd: int) -> None:
        """Send a command byte (Rs = 0)."""
        self._send_byte(cmd, 0)

    def _send_data(self, data: int) -> None:
        """Send a data byte (Rs = 1)."""
        self._send_byte(data, self.Rs)

    # ─────────────────────────── INIT (from OLD tested code) ─────────────────

    def _initialize(self) -> None:
        """
        Initialize the LCD into 4-bit mode using the standard
        HD44780 reset sequence (battle-tested from old code).
        """
        try:
            # Power-on delay — many LCDs need >40ms
            time.sleep(0.1)

            # Send 0x03 three times to ensure known state
            # (handles interrupted or partial previous inits)
            self._send_nibble(0x30)
            time.sleep(0.005)
            self._send_nibble(0x30)
            time.sleep(0.005)
            self._send_nibble(0x30)
            time.sleep(0.005)

            # Switch to 4-bit mode
            self._send_nibble(0x20)
            time.sleep(0.005)

            # Full init in 4-bit mode
            self._send_command(
                self.LCD_FUNCTIONSET |
                self.LCD_4BITMODE   |
                self.LCD_2LINE      |
                self.LCD_5x8DOTS
            )
            time.sleep(0.005)

            self._send_command(
                self.LCD_DISPLAYCONTROL |
                self.LCD_DISPLAYON      |
                self.LCD_CURSOROFF      |
                self.LCD_BLINKOFF
            )
            time.sleep(0.002)

            self.clear()

            self._send_command(
                self.LCD_ENTRYMODESET        |
                self.LCD_ENTRYLEFT           |
                self.LCD_ENTRYSHIFTDECREMENT
            )
            time.sleep(0.002)

        except Exception as e:
            raise LCDError(f"LCD initialization failed: {e}")

    # ─────────────────────────── CORE PUBLIC API ─────────────────────────────

    def clear(self) -> None:
        """Clear the entire display."""
        self._send_command(self.LCD_CLEARDISPLAY)
        time.sleep(0.003)

    def home(self) -> None:
        """Move cursor to position (0, 0)."""
        self._send_command(self.LCD_RETURNHOME)
        time.sleep(0.003)

    def set_cursor(self, col: int, row: int) -> None:
        """
        Move cursor to (col, row).

        Args:
            col: Column index (0-based)
            row: Row index (0-based)
        """
        row = min(max(row, 0), self.rows - 1)
        col = min(max(col, 0), self.cols - 1)
        self._send_command(self.LCD_SETDDRAMADDR | (col + self.row_offsets[row]))

    def write(self, text: str) -> None:
        """Write text at current cursor position."""
        for ch in str(text):
            self._send_data(ord(ch))

    def write_at(self, col: int, row: int, text: str) -> None:
        """
        Write text at a specific position.

        Args:
            col:  Column position (0-based)
            row:  Row position (0-based)
            text: Text to write
        """
        self.set_cursor(col, row)
        self.write(text)

    # ─────────────────────────── SHOW API (from NEW design) ──────────────────

    def show(
        self,
        content     : "str | List[str]",
        duration    : Optional[float] = None,
        clear_first : bool            = True,
        center      : bool            = False
    ) -> None:
        """
        Display content on LCD.

        Args:
            content:     Single string or list of strings (one per row)
            duration:    Auto-clear after N seconds (None = no auto-clear)
            clear_first: Clear display before writing
            center:      Center text on each row

        Examples:
            lcd.show("Hello!")
            lcd.show(["Line 1", "Line 2", "Line 3"])
            lcd.show("Please wait...", duration=2)
            lcd.show("MENU", center=True)
        """
        if clear_first:
            self.clear()

        lines = [content] if isinstance(content, str) else content

        for i, line in enumerate(lines[:self.rows]):
            line = str(line)
            if center:
                padding = (self.cols - len(line)) // 2
                line = " " * padding + line
            line = line[:self.cols]
            self.write_at(0, i, line.ljust(self.cols))

        if duration:
            time.sleep(duration)
            self.clear()

    # ─────────────────────────── SCROLLABLE (from NEW design) ────────────────

    def _render_scroll_view(
        self,
        lines                 : List[str],
        offset                : int,
        title                 : Optional[str] = None,
        show_scroll_indicator : bool          = True,
    ) -> None:
        """
        Internal helper — renders one page of a scrollable list.

        Layout with title:    Row 0 = title, Rows 1+ = content
        Layout without title: Rows 0+ = content
        """
        self.clear()

        content_start_row = 0
        if title is not None:
            self.write_at(0, 0, title[:self.cols].center(self.cols))
            content_start_row = 1

        visible_rows = self.rows - content_start_row
        total        = len(lines)

        for i in range(visible_rows):
            line_index = offset + i
            if line_index >= total:
                break

            line = lines[line_index][:self.cols]

            indicator = " "
            if show_scroll_indicator:
                if i == 0 and offset > 0:
                    indicator = "^"
                elif i == visible_rows - 1 and (offset + visible_rows) < total:
                    indicator = "v"

            display_line = f"{line:<{self.cols - 1}}{indicator}"
            self.write_at(0, content_start_row + i, display_line)

    def show_scrollable(
        self,
        lines                 : List[str],
        title                 : Optional[str] = None,
        scroll_up_key         : str           = "2",
        scroll_down_key       : str           = "8",
        exit_key              : str           = "#",
        keypad                                = None,
        get_key_func          : Optional[Callable] = None,
        show_scroll_indicator : bool          = True,
    ) -> Optional[int]:
        """
        Display a scrollable list longer than the LCD row count.

        Pass either:
          - keypad       – object with a .read_key() method
          - get_key_func – any callable() that returns a key str or None

        Falls back to terminal input() if neither is provided (for testing).

        Args:
            lines:                List of text lines (any length)
            title:                Optional fixed header on row 0
            scroll_up_key:        Key to scroll up   (default '2')
            scroll_down_key:      Key to scroll down (default '8')
            exit_key:             Key to exit        (default '#')
            keypad:               Object with .read_key() method
            get_key_func:         Callable() → str | None
            show_scroll_indicator: Show '^'/'v' hint characters

        Returns:
            Current scroll offset when user pressed exit_key, or None
        """
        if not lines:
            self.show("(empty list)")
            return None

        if get_key_func is not None:
            _get_key = get_key_func
        elif keypad is not None:
            _get_key = keypad.read_key
        else:
            def _get_key():
                return input("Key [2=up 8=down #=exit]: ").strip() or None

        content_start_row = 1 if title is not None else 0
        visible_rows      = self.rows - content_start_row
        total             = len(lines)
        offset            = 0

        self._render_scroll_view(lines, offset, title, show_scroll_indicator)

        while True:
            key = _get_key()
            if key is None:
                continue

            if key == scroll_down_key:
                if offset + visible_rows < total:
                    offset += 1
                    self._render_scroll_view(lines, offset, title, show_scroll_indicator)

            elif key == scroll_up_key:
                if offset > 0:
                    offset -= 1
                    self._render_scroll_view(lines, offset, title, show_scroll_indicator)

            elif key == exit_key:
                break

        return offset

    def show_scrollable_menu(
        self,
        title           : str,
        options         : List[str],
        scroll_up_key   : str              = "2",
        scroll_down_key : str              = "8",
        select_key      : str              = "*",
        exit_key        : str              = "#",
        keypad                             = None,
        get_key_func    : Optional[Callable] = None,
        cursor_char     : str              = ">",
    ) -> Optional[int]:
        """
        Interactive scrollable menu with a cursor — returns selected index.

        Args:
            title:           Fixed header row
            options:         List of option strings (any length)
            scroll_up_key:   Move cursor up   (default '2')
            scroll_down_key: Move cursor down (default '8')
            select_key:      Confirm selection (default '*')
            exit_key:        Abort without selecting (default '#')
            keypad:          Object with .read_key() method
            get_key_func:    Callable() → str | None
            cursor_char:     Character shown left of focused option

        Returns:
            Index of selected option (0-based), or None if aborted

        Example:
            choice = lcd.show_scrollable_menu(
                title="SELECT MODE",
                options=["[1] Scan", "[2] Check", "[3] Export", "[4] Settings"],
                keypad=keypad
            )
            if choice is not None:
                print(f"Selected: {options[choice]}")
        """
        if not options:
            self.show("(no options)")
            return None

        if get_key_func is not None:
            _get_key = get_key_func
        elif keypad is not None:
            _get_key = keypad.read_key
        else:
            def _get_key():
                return input(
                    f"Key [{scroll_up_key}=up {scroll_down_key}=down "
                    f"{select_key}=select {exit_key}=exit]: "
                ).strip() or None

        content_start_row = 1
        visible_rows      = self.rows - content_start_row
        total             = len(options)
        cursor            = 0
        offset            = 0

        def _render():
            self.clear()
            self.write_at(0, 0, title[:self.cols].center(self.cols))

            for i in range(visible_rows):
                line_index = offset + i
                if line_index >= total:
                    break

                prefix       = cursor_char if line_index == cursor else " "
                max_text_len = self.cols - 2

                hint = " "
                if i == 0 and offset > 0:
                    hint = "^"
                elif i == visible_rows - 1 and (offset + visible_rows) < total:
                    hint = "v"

                display_line = f"{prefix}{options[line_index][:max_text_len]:<{max_text_len}}{hint}"
                self.write_at(0, content_start_row + i, display_line)

        _render()

        while True:
            key = _get_key()
            if key is None:
                continue

            if key == scroll_down_key:
                if cursor < total - 1:
                    cursor += 1
                    if cursor >= offset + visible_rows:
                        offset += 1
                    _render()

            elif key == scroll_up_key:
                if cursor > 0:
                    cursor -= 1
                    if cursor < offset:
                        offset -= 1
                    _render()

            elif key == select_key:
                return cursor

            elif key == exit_key:
                return None

    def show_menu(
        self,
        title       : str,
        options     : List[str],
        clear_first : bool = True
    ) -> None:
        """
        Display a static menu (no scrolling).
        For menus longer than available rows, use show_scrollable_menu().

        Args:
            title:       Menu title (row 0)
            options:     List of menu options
            clear_first: Clear display first

        Example:
            lcd.show_menu("HOME MENU", [
                "[1] Scan Answer Key",
                "[2] Check Sheets",
                "[3] Settings"
            ])
        """
        if clear_first:
            self.clear()

        self.write_at(0, 0, title.center(self.cols))

        if self.rows >= 2:
            self.write_at(0, 1, "=" * self.cols)

        start_row = 2 if self.rows >= 4 else 1
        for i, option in enumerate(options):
            if start_row + i < self.rows:
                self.write_at(0, start_row + i, option[:self.cols])

    # ─────────────────────────── DISPLAY CONTROL ─────────────────────────────

    def backlight_on(self) -> None:
        """Turn backlight on"""
        self.backlight_state = self.LCD_BACKLIGHT
        self._i2c_write(0)

    def backlight_off(self) -> None:
        """Turn backlight off"""
        self.backlight_state = self.LCD_NOBACKLIGHT
        self._i2c_write(0)

    def display_on(self) -> None:
        self._send_command(self.LCD_DISPLAYCONTROL | self.LCD_DISPLAYON | self.LCD_CURSOROFF | self.LCD_BLINKOFF)

    def display_off(self) -> None:
        self._send_command(self.LCD_DISPLAYCONTROL | self.LCD_DISPLAYOFF)

    def cursor_on(self) -> None:
        self._send_command(self.LCD_DISPLAYCONTROL | self.LCD_DISPLAYON | self.LCD_CURSORON | self.LCD_BLINKOFF)

    def cursor_off(self) -> None:
        self._send_command(self.LCD_DISPLAYCONTROL | self.LCD_DISPLAYON | self.LCD_CURSOROFF | self.LCD_BLINKOFF)

    def blink_on(self) -> None:
        self._send_command(self.LCD_DISPLAYCONTROL | self.LCD_DISPLAYON | self.LCD_CURSORON | self.LCD_BLINKON)

    def blink_off(self) -> None:
        self._send_command(self.LCD_DISPLAYCONTROL | self.LCD_DISPLAYON | self.LCD_CURSORON | self.LCD_BLINKOFF)

    def scroll_left(self) -> None:
        self._send_command(self.LCD_CURSORSHIFT | self.LCD_DISPLAYMOVE | self.LCD_MOVELEFT)

    def scroll_right(self) -> None:
        self._send_command(self.LCD_CURSORSHIFT | self.LCD_DISPLAYMOVE | self.LCD_MOVERIGHT)

    # ─────────────────────────── CUSTOM CHARACTERS ───────────────────────────

    def create_char(self, location: int, charmap: List[int]) -> None:
        """
        Define a custom character in CGRAM.

        Args:
            location: Slot 0–7
            charmap:  List of 8 bytes (each byte = one row of 5 pixels)

        Example:
            heart = [0b00000, 0b01010, 0b11111, 0b11111,
                     0b01110, 0b00100, 0b00000, 0b00000]
            lcd.create_char(0, heart)
            lcd.write(chr(0))
        """
        location &= 0x07
        self._send_command(self.LCD_SETCGRAMADDR | (location << 3))
        for byte in charmap:
            self._send_data(byte)

    # ─────────────────────────── UTILS ───────────────────────────────────────

    def get_size(self) -> Tuple[int, int]:
        """Get LCD size as (cols, rows)"""
        return (self.cols, self.rows)

    def close(self) -> None:
        """Clear display, turn off backlight, close I2C bus."""
        try:
            self.clear()
            self.backlight_off()
        except Exception:
            pass
        self.bus.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self) -> str:
        return f"LCD_I2C(address=0x{self.address:02X}, size={self.cols}x{self.rows})"


# ─────────────────────────── MODULE-LEVEL SINGLETON ──────────────────────────
# Kept from OLD code for backwards compatibility with existing callers.

_lcd: Optional[LCD_I2C] = None


def setup_lcd(
    addr : int     = 0x27,
    bus  : int     = 1,
    cols : int     = 16,
    rows : int     = 2
) -> LCD_I2C:
    """
    Create and return the global LCD instance (call once at startup).

    Args:
        addr: I2C address (0x27 or 0x3F)
        bus:  I2C bus number (1 on most Raspberry Pi models)
        cols: Display width in characters
        rows: Display height in characters

    Returns:
        LCD_I2C instance
    """
    global _lcd
    try:
        size = LCDSize.LCD_20x4 if (cols == 20 and rows == 4) else LCDSize.LCD_16x2
        _lcd = LCD_I2C(address=addr, bus=bus, size=size)
        return _lcd
    except Exception as e:
        raise RuntimeError(
            f"Failed to setup LCD: {e}\n"
            f"Verify I2C address with: i2cdetect -y 1"
        )


def get_lcd() -> LCD_I2C:
    """Return the global LCD instance (raises if not yet set up)."""
    if _lcd is None:
        raise RuntimeError("LCD not initialized. Call setup_lcd() first.")
    return _lcd


def cleanup_lcd() -> None:
    """Clear display, turn off backlight, and release the global instance."""
    global _lcd
    if _lcd:
        try:
            _lcd.close()
        except Exception:
            pass
        _lcd = None


def lcd_print(line1="", line2="", line3="", line4="") -> None:
    """Display a multi-line message (no-op if LCD is not initialized)."""
    if _lcd:
        _lcd.show([line1, line2, line3, line4])


def lcd_clear() -> None:
    """Clear the display (no-op if LCD is not initialized)."""
    if _lcd:
        _lcd.clear()


# ─────────────────────────── I2C SCANNER ─────────────────────────────────────

def detect_i2c_address(bus: int = 1) -> List[int]:
    """
    Scan I2C bus for connected devices.

    Args:
        bus: I2C bus number

    Returns:
        List of detected I2C addresses
    """
    devices = []
    try:
        i2c_bus = smbus2.SMBus(bus)
        for address in range(0x03, 0x78):
            try:
                i2c_bus.read_byte(address)
                devices.append(address)
            except Exception:
                pass
        i2c_bus.close()
    except Exception as e:
        print(f"Error scanning I2C bus: {e}")
    return devices


# ─────────────────────────── USAGE EXAMPLES ──────────────────────────────────

if __name__ == "__main__":

    print("=== LCD_I2C Test ===")
    print("Scanning for I2C devices...")
    found = detect_i2c_address()
    print(f"Found: {[hex(a) for a in found]}")
    print()

    # ── Instantiate ──────────────────────────────────────────────────────
    lcd = LCD_I2C(address=0x27, size=LCDSize.LCD_20x4)

    # ── Test 1: Simple single-line message ───────────────────────────────
    print("[Test 1] Single line...")
    lcd.show("Hello, World!")
    time.sleep(2)

    # ── Test 2: Multi-line message ───────────────────────────────────────
    print("[Test 2] Multi-line...")
    lcd.show(["Line 1", "Line 2", "Line 3", "Line 4"])
    time.sleep(2)

    # ── Test 3: Centered text ────────────────────────────────────────────
    print("[Test 3] Centered...")
    lcd.show("CENTERED", center=True)
    time.sleep(2)

    # ── Test 4: Temporary message (auto-clears) ──────────────────────────
    print("[Test 4] Temporary message (2s)...")
    lcd.show("Auto-clear in 2s", duration=2)

    # ── Test 5: write_at positional write ────────────────────────────────
    print("[Test 5] write_at...")
    lcd.clear()
    lcd.write_at(0, 0, "Top Left")
    lcd.write_at(12, 1, "Bot Right")
    time.sleep(2)

    # ── Test 6: Static menu ──────────────────────────────────────────────
    print("[Test 6] Static menu...")
    lcd.show_menu("HOME MENU", ["[1] Start", "[2] Settings"])
    time.sleep(2)

    # ── Test 7: Scrollable list (terminal fallback, no keypad needed) ────
    print("[Test 7] Scrollable list (use 2/8/# in terminal)...")
    lcd.show_scrollable(
        lines=["Alice  48/50", "Bob    45/50", "Carol  50/50",
               "Dave   40/50", "Eve    47/50", "Frank  43/50"],
        title="SCORES"
    )

    # ── Test 8: Scrollable menu (terminal fallback) ──────────────────────
    print("[Test 8] Scrollable menu (use 2/8/*/# in terminal)...")
    choice = lcd.show_scrollable_menu(
        title="SELECT MODE",
        options=["[1] Scan", "[2] Check", "[3] Export", "[4] Settings", "[5] About"]
    )
    print(f"  Selected index: {choice}")

    # ── Test 9: Singleton pattern (backwards compat) ─────────────────────
    print("[Test 9] Singleton pattern...")
    setup_lcd(addr=0x27, cols=20, rows=4)
    lcd_print("Singleton works!", "Line 2", "Line 3")
    time.sleep(2)
    cleanup_lcd()

    lcd.close()
    print("=== Done ===")