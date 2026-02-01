"""
LCD Controller for I2C LCD Display
Supports 16x2 and 20x4 character LCD displays with PCF8574 I2C backpack
"""
import smbus
import time
import logging

logger = logging.getLogger(__name__)

# LCD I2C address (common addresses: 0x27 or 0x3F)
# You can find yours by running: i2cdetect -y 1
LCD_I2C_ADDR = 0x27

# LCD Commands
LCD_CLEARDISPLAY = 0x01
LCD_RETURNHOME = 0x02
LCD_ENTRYMODESET = 0x04
LCD_DISPLAYCONTROL = 0x08
LCD_CURSORSHIFT = 0x10
LCD_FUNCTIONSET = 0x20
LCD_SETCGRAMADDR = 0x40
LCD_SETDDRAMADDR = 0x80

# Flags for display entry mode
LCD_ENTRYRIGHT = 0x00
LCD_ENTRYLEFT = 0x02
LCD_ENTRYSHIFTINCREMENT = 0x01
LCD_ENTRYSHIFTDECREMENT = 0x00

# Flags for display on/off control
LCD_DISPLAYON = 0x04
LCD_DISPLAYOFF = 0x00
LCD_CURSORON = 0x02
LCD_CURSOROFF = 0x00
LCD_BLINKON = 0x01
LCD_BLINKOFF = 0x00

# Flags for display/cursor shift
LCD_DISPLAYMOVE = 0x08
LCD_CURSORMOVE = 0x00
LCD_MOVERIGHT = 0x04
LCD_MOVELEFT = 0x00

# Flags for function set
LCD_8BITMODE = 0x10
LCD_4BITMODE = 0x00
LCD_2LINE = 0x08
LCD_1LINE = 0x00
LCD_5x10DOTS = 0x04
LCD_5x8DOTS = 0x00

# Flags for backlight control
LCD_BACKLIGHT = 0x08
LCD_NOBACKLIGHT = 0x00

# Enable bit
En = 0b00000100
Rw = 0b00000010
Rs = 0b00000001


class LCD_I2C:
    """
    I2C LCD Display Controller
    
    Supports standard I2C LCD displays with PCF8574 backpack adapter.
    Common sizes: 16x2, 20x4
    """
    
    def __init__(self, addr=LCD_I2C_ADDR, bus=1, cols=16, rows=2):
        """
        Initialize LCD display.
        
        Args:
            addr: I2C address (default 0x27, also try 0x3F if not working)
            bus: I2C bus number (default 1 for Raspberry Pi)
            cols: Number of columns (default 16)
            rows: Number of rows (default 2)
        """
        self.addr = addr
        self.bus_num = bus
        self.cols = cols
        self.rows = rows
        self.backlight_state = LCD_BACKLIGHT
        
        try:
            self.bus = smbus.SMBus(bus)
            logger.info(f"LCD I2C initialized on address 0x{addr:02X}")
            
            # Initialize display
            self._init_display()
            
        except Exception as e:
            logger.error(f"Failed to initialize LCD: {e}")
            raise
    
    def _init_display(self):
        """Initialize the LCD in 4-bit mode."""
        # Wait for display to power up
        time.sleep(0.05)
        
        # Put the LCD into 4-bit mode
        self._write4bits(0x03 << 4)
        time.sleep(0.005)
        
        self._write4bits(0x03 << 4)
        time.sleep(0.005)
        
        self._write4bits(0x03 << 4)
        time.sleep(0.00015)
        
        self._write4bits(0x02 << 4)
        
        # Set display parameters
        self._send_command(LCD_FUNCTIONSET | LCD_4BITMODE | LCD_2LINE | LCD_5x8DOTS)
        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF)
        self.clear()
        self._send_command(LCD_ENTRYMODESET | LCD_ENTRYLEFT | LCD_ENTRYSHIFTDECREMENT)
        
        time.sleep(0.002)
        logger.info("LCD display initialized successfully")
    
    def _write4bits(self, data):
        """Write 4 bits to the display."""
        try:
            self.bus.write_byte(self.addr, data | self.backlight_state)
            self._pulse_enable(data)
        except Exception as e:
            logger.error(f"Error writing to LCD: {e}")
    
    def _pulse_enable(self, data):
        """Pulse the enable bit to latch data."""
        try:
            self.bus.write_byte(self.addr, data | En | self.backlight_state)
            time.sleep(0.0005)
            
            self.bus.write_byte(self.addr, (data & ~En) | self.backlight_state)
            time.sleep(0.0001)
        except Exception as e:
            logger.error(f"Error pulsing enable: {e}")
    
    def _send_command(self, cmd):
        """Send command to LCD."""
        self._send_byte(cmd, 0)
    
    def _send_data(self, data):
        """Send data to LCD."""
        self._send_byte(data, Rs)
    
    def _send_byte(self, data, mode):
        """Send byte in 4-bit mode."""
        high_bits = mode | (data & 0xF0)
        low_bits = mode | ((data << 4) & 0xF0)
        
        self._write4bits(high_bits)
        self._write4bits(low_bits)
    
    def clear(self):
        """Clear the display."""
        self._send_command(LCD_CLEARDISPLAY)
        time.sleep(0.002)
    
    def home(self):
        """Return cursor to home position."""
        self._send_command(LCD_RETURNHOME)
        time.sleep(0.002)
    
    def set_cursor(self, col, row):
        """
        Set cursor position.
        
        Args:
            col: Column (0-indexed)
            row: Row (0-indexed)
        """
        row_offsets = [0x00, 0x40, 0x14, 0x54]
        if row >= self.rows:
            row = self.rows - 1
        
        self._send_command(LCD_SETDDRAMADDR | (col + row_offsets[row]))
    
    def print(self, text):
        """
        Print text at current cursor position.
        
        Args:
            text: String to print
        """
        for char in str(text):
            self._send_data(ord(char))
    
    def print_line(self, text, row=0, align='left'):
        """
        Print text on a specific row with alignment.
        
        Args:
            text: String to print
            row: Row number (0-indexed)
            align: 'left', 'center', or 'right'
        """
        text = str(text)
        
        # Truncate if too long
        if len(text) > self.cols:
            text = text[:self.cols]
        
        # Align text
        if align == 'center':
            padding = (self.cols - len(text)) // 2
            text = ' ' * padding + text
        elif align == 'right':
            padding = self.cols - len(text)
            text = ' ' * padding + text
        
        # Pad to fill entire row
        text = text.ljust(self.cols)
        
        self.set_cursor(0, row)
        self.print(text)
    
    def display_message(self, line1="", line2="", line3="", line4=""):
        """
        Display up to 4 lines of text (clear display first).
        
        Args:
            line1-4: Text for each line
        """
        self.clear()
        
        lines = [line1, line2, line3, line4]
        for i, line in enumerate(lines[:self.rows]):
            if line:
                self.print_line(line, row=i)
    
    def backlight_on(self):
        """Turn backlight on."""
        self.backlight_state = LCD_BACKLIGHT
        self._write4bits(0)
    
    def backlight_off(self):
        """Turn backlight off."""
        self.backlight_state = LCD_NOBACKLIGHT
        self._write4bits(0)
    
    def display_on(self):
        """Turn display on."""
        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF)
    
    def display_off(self):
        """Turn display off."""
        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYOFF | LCD_CURSOROFF | LCD_BLINKOFF)
    
    def cursor_on(self):
        """Show cursor."""
        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSORON | LCD_BLINKOFF)
    
    def cursor_off(self):
        """Hide cursor."""
        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF)
    
    def blink_on(self):
        """Turn cursor blink on."""
        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSORON | LCD_BLINKON)
    
    def blink_off(self):
        """Turn cursor blink off."""
        self._send_command(LCD_DISPLAYCONTROL | LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF)
    
    def scroll_left(self):
        """Scroll display left."""
        self._send_command(LCD_CURSORSHIFT | LCD_DISPLAYMOVE | LCD_MOVELEFT)
    
    def scroll_right(self):
        """Scroll display right."""
        self._send_command(LCD_CURSORSHIFT | LCD_DISPLAYMOVE | LCD_MOVERIGHT)
    
    def create_char(self, location, charmap):
        """
        Create custom character.
        
        Args:
            location: Character location (0-7)
            charmap: List of 8 bytes defining character pattern
        """
        location &= 0x7  # Only 8 locations (0-7)
        self._send_command(LCD_SETCGRAMADDR | (location << 3))
        for i in range(8):
            self._send_data(charmap[i])


# Global LCD instance
_lcd = None


def setup_lcd(addr=0x27, bus=1, cols=16, rows=2):
    """
    Setup LCD display (call once at startup).
    
    Args:
        addr: I2C address (0x27 or 0x3F)
        bus: I2C bus number (default 1)
        cols: Number of columns (default 16)
        rows: Number of rows (default 2)
    
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
        logger.error("Check I2C address with: i2cdetect -y 1")
        raise


def get_lcd():
    """Get the LCD instance."""
    if _lcd is None:
        raise RuntimeError("LCD not initialized. Call setup_lcd() first.")
    return _lcd


def cleanup_lcd():
    """Clean up LCD resources."""
    global _lcd
    if _lcd:
        try:
            _lcd.clear()
            _lcd.backlight_off()
            logger.info("LCD cleaned up")
        except:
            pass
        _lcd = None


# Convenience functions
def lcd_print(line1="", line2="", line3="", line4=""):
    """Quick function to display message on LCD."""
    if _lcd:
        _lcd.display_message(line1, line2, line3, line4)


def lcd_clear():
    """Quick function to clear LCD."""
    if _lcd:
        _lcd.clear()