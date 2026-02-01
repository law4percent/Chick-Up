"""
LCD Controller for I2C LCD Display
Supports 16x2 and 20x4 character LCD displays with PCF8574 I2C backpack
"""
import smbus
import time
import logging

logger = logging.getLogger(__name__)

# LCD I2C address (common addresses: 0x27 or 0x3F)
LCD_I2C_ADDR = 0x27

# LCD Commands
LCD_CLEARDISPLAY    = 0x01
LCD_RETURNHOME      = 0x02
LCD_ENTRYMODESET    = 0x04
LCD_DISPLAYCONTROL  = 0x08
LCD_CURSORSHIFT     = 0x10
LCD_FUNCTIONSET     = 0x20
LCD_SETCGRAMADDR    = 0x40
LCD_SETDDRAMADDR    = 0x80

# Entry mode flags
LCD_ENTRYLEFT            = 0x02
LCD_ENTRYSHIFTDECREMENT  = 0x00

# Display control flags
LCD_DISPLAYON   = 0x04
LCD_DISPLAYOFF  = 0x00
LCD_CURSORON    = 0x02
LCD_CURSOROFF   = 0x00
LCD_BLINKON     = 0x01
LCD_BLINKOFF    = 0x00

# Cursor/display shift flags
LCD_DISPLAYMOVE = 0x08
LCD_MOVERIGHT   = 0x04
LCD_MOVELEFT    = 0x00

# Function set flags
LCD_4BITMODE  = 0x00
LCD_2LINE     = 0x08
LCD_5x8DOTS   = 0x00

# Backlight
LCD_BACKLIGHT   = 0x08
LCD_NOBACKLIGHT = 0x00

# PCF8574 bit positions
En = 0x04   # Enable bit
Rs = 0x01   # Register select bit


class LCD_I2C:
    """
    I2C LCD Display Controller for PCF8574 backpack.
    Common sizes: 16x2, 20x4.
    """

    def __init__(self, addr=LCD_I2C_ADDR, bus=1, cols=16, rows=2):
        self.addr = addr
        self.cols = cols
        self.rows = rows
        self.backlight_state = LCD_BACKLIGHT

        try:
            self.bus = smbus.SMBus(bus)
            logger.info(f"LCD I2C initialized on address 0x{addr:02X}")
            self._init_display()
        except Exception as e:
            logger.error(f"Failed to initialize LCD: {e}")
            raise

    # ─────────────────────────── LOW-LEVEL I2C ───────────────────────────
    def _i2c_write(self, data):
        """Write a single byte to the I2C bus."""
        self.bus.write_byte(self.addr, data | self.backlight_state)

    def _pulse_enable(self, data):
        """Pulse the EN pin high then low to latch the nibble."""
        self._i2c_write(data | En)
        time.sleep(0.0005)          # EN high pulse (500µs, safe margin)
        self._i2c_write(data & ~En)
        time.sleep(0.0005)          # EN low hold

    def _send_nibble(self, nibble):
        """Send a single nibble (must already be in the upper 4 bits)."""
        self._i2c_write(nibble)
        self._pulse_enable(nibble)

    # ─────────────────────────── BYTE SEND ───────────────────────────────
    def _send_byte(self, data, mode):
        """
        Send a full byte in 4-bit mode: high nibble first, then low nibble.

        Args:
            data: Byte value (0x00–0xFF)
            mode: 0 for command, Rs for character data
        """
        self._send_nibble(mode | (data & 0xF0))          # high nibble already in upper position
        self._send_nibble(mode | ((data & 0x0F) << 4))   # low nibble shifted to upper position
        time.sleep(0.0005)  # command execution delay

    def _send_command(self, cmd):
        """Send a command byte (Rs = 0)."""
        self._send_byte(cmd, 0)

    def _send_data(self, data):
        """Send a data byte (Rs = 1)."""
        self._send_byte(data, Rs)

    # ─────────────────────────── INIT SEQUENCE ───────────────────────────
    def _init_display(self):
        """
        Initialize the LCD into 4-bit mode using the standard
        reset sequence from the HD44780 datasheet.
        """
        # Power-on reset delay — many LCDs need >40ms
        time.sleep(0.1)

        # The HD44780 starts in 8-bit mode.
        # Sending 0x03 three times ensures we're in a known state
        # regardless of whether a previous init was interrupted.
        self._send_nibble(0x30)     # 0x03 in upper nibble
        time.sleep(0.005)
        self._send_nibble(0x30)
        time.sleep(0.005)
        self._send_nibble(0x30)
        time.sleep(0.005)

        # Now switch to 4-bit mode
        self._send_nibble(0x20)     # 0x02 in upper nibble
        time.sleep(0.005)

        # From here on we can send full bytes in 4-bit mode
        self._send_command(LCD_FUNCTIONSET | LCD_4BITMODE | LCD_2LINE | LCD_5x8DOTS)
        time.sleep(0.005)

        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF)
        time.sleep(0.002)

        self.clear()

        self._send_command(LCD_ENTRYMODESET | LCD_ENTRYLEFT | LCD_ENTRYSHIFTDECREMENT)
        time.sleep(0.002)

        logger.info("LCD display initialized successfully")

    # ─────────────────────────── PUBLIC API ──────────────────────────────
    def clear(self):
        """Clear the entire display."""
        self._send_command(LCD_CLEARDISPLAY)
        time.sleep(0.003)   # clear takes up to 1.53ms

    def home(self):
        """Move cursor to position (0, 0)."""
        self._send_command(LCD_RETURNHOME)
        time.sleep(0.003)

    def set_cursor(self, col, row):
        """
        Move cursor to (col, row).

        Args:
            col: Column index (0-based)
            row: Row index (0-based)
        """
        row_offsets = [0x00, 0x40, 0x14, 0x54]
        row = min(row, self.rows - 1)
        col = min(col, self.cols - 1)
        self._send_command(LCD_SETDDRAMADDR | (col + row_offsets[row]))

    def print(self, text):
        """Write text at the current cursor position."""
        for ch in str(text):
            self._send_data(ord(ch))

    def print_line(self, text, row=0, align='left'):
        """
        Write text on a specific row, optionally aligned.

        Args:
            text:  String to display
            row:   Row index (0-based)
            align: 'left' | 'center' | 'right'
        """
        text = str(text)[:self.cols]   # truncate to display width

        if align == 'center':
            pad = (self.cols - len(text)) // 2
            text = ' ' * pad + text
        elif align == 'right':
            text = text.rjust(self.cols)

        # Pad to full row width so old characters are overwritten
        text = text.ljust(self.cols)

        self.set_cursor(0, row)
        self.print(text)

    def display_message(self, line1="", line2="", line3="", line4=""):
        """
        Clear display and show up to 4 lines of text.

        Args:
            line1–line4: Text for each row (extras ignored if display is smaller)
        """
        self.clear()
        for i, text in enumerate([line1, line2, line3, line4][:self.rows]):
            if text:
                self.print_line(text, row=i)

    # ─────────────────────────── BACKLIGHT / DISPLAY CONTROL ─────────────
    def backlight_on(self):
        self.backlight_state = LCD_BACKLIGHT
        self._i2c_write(0)

    def backlight_off(self):
        self.backlight_state = LCD_NOBACKLIGHT
        self._i2c_write(0)

    def display_on(self):
        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF)

    def display_off(self):
        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYOFF | LCD_CURSOROFF | LCD_BLINKOFF)

    def cursor_on(self):
        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSORON | LCD_BLINKOFF)

    def cursor_off(self):
        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF)

    def blink_on(self):
        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSORON | LCD_BLINKON)

    def blink_off(self):
        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF)

    def scroll_left(self):
        self._send_command(LCD_CURSORSHIFT | LCD_DISPLAYMOVE | LCD_MOVELEFT)

    def scroll_right(self):
        self._send_command(LCD_CURSORSHIFT | LCD_DISPLAYMOVE | LCD_MOVERIGHT)

    # ─────────────────────────── CUSTOM CHARACTERS ───────────────────────
    def create_char(self, location, charmap):
        """
        Define a custom character in CGRAM.

        Args:
            location: Slot 0–7
            charmap:  List of 8 bytes (each byte = one row of 5 pixels)
        """
        location &= 0x07
        self._send_command(LCD_SETCGRAMADDR | (location << 3))
        for byte in charmap:
            self._send_data(byte)


# ========================= MODULE-LEVEL SINGLETON ========================
_lcd = None


def setup_lcd(addr=0x27, bus=1, cols=16, rows=2):
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
        _lcd = LCD_I2C(addr=addr, bus=bus, cols=cols, rows=rows)
        logger.info(f"LCD setup complete: {cols}x{rows} at 0x{addr:02X}")
        return _lcd
    except Exception as e:
        logger.error(f"Failed to setup LCD: {e}")
        logger.error("Verify I2C address with: i2cdetect -y 1")
        raise


def get_lcd():
    """Return the global LCD instance (raises if not yet set up)."""
    if _lcd is None:
        raise RuntimeError("LCD not initialized. Call setup_lcd() first.")
    return _lcd


def cleanup_lcd():
    """Clear display, turn off backlight, and release the global instance."""
    global _lcd
    if _lcd:
        try:
            _lcd.clear()
            _lcd.backlight_off()
            logger.info("LCD cleaned up")
        except Exception:
            pass
        _lcd = None


# ─── Convenience wrappers ────────────────────────────────────────────────
def lcd_print(line1="", line2="", line3="", line4=""):
    """Display a multi-line message (no-op if LCD is not initialized)."""
    if _lcd:
        _lcd.display_message(line1, line2, line3, line4)


def lcd_clear():
    """Clear the display (no-op if LCD is not initialized)."""
    if _lcd:
        _lcd.clear()