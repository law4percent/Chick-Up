import RPi.GPIO as GPIO
import time


DEFAULT_ROW_PINS = [4, 21, 20, 16]    # GPIO 19 → GPIO 4
DEFAULT_COL_PINS = [12, 18, 26, 23]   # GPIO 22 → GPIO 18, GPIO 6 → GPIO 26
ROW_PINS = DEFAULT_ROW_PINS
COL_PINS = DEFAULT_COL_PINS
# LEFT motor
LEFT_IN1 = 17
LEFT_IN2 = 27

# RIGHT motor
RIGHT_IN1 = 22
RIGHT_IN2 = 23
LEFT_TRIG = 25
LEFT_ECHO = 24
RIGHT_TRIG = 7
RIGHT_ECHO = 8
MATRIX = [
    ['1','2','3','A'],
    ['4','5','6','B'],
    ['7','8','9','C'],
    ['*','0','#','D'] 
]

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Setup pins
for r in ROW_PINS:
    GPIO.setup(r, GPIO.OUT)
    # Output is set LOW during scan_key, so setting HIGH here is a safe default (pulling up)
    GPIO.output(r, GPIO.HIGH) 

for c in COL_PINS:
    # Set column pins as inputs with internal pull-up resistors
    GPIO.setup(c, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def scan_key():
    for i, r in enumerate(ROW_PINS):
        # 1. Activate the current Row (pull it LOW)
        GPIO.output(r, GPIO.LOW)
        time.sleep(0.002) # Short delay for stability

        for j, c in enumerate(COL_PINS):
            # 2. Check if the Column is pulled LOW by the keypress
            if GPIO.input(c) == GPIO.LOW:
                # Key is pressed
                
                # 3. Immediately deactivate the Row to avoid registering multiple presses
                # (This is already done correctly in your original code)
                GPIO.output(r, GPIO.HIGH) 
                
                # 4. Return the key value
                return MATRIX[i][j]

        # 5. Deactivate the Row before moving to the next one
        GPIO.output(r, GPIO.HIGH)
        
    return None


print("Keypad ready")

try:
    last_key = None
    while True:
        key = scan_key()
        if key and key != last_key:
            print("Pressed:", key)
            last_key = key
        # Handle key release (optional, but good for reliable single presses)
        elif not key:
            last_key = None
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nExiting and cleaning up GPIO...")
    GPIO.cleanup()
