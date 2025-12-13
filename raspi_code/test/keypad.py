from gpiozero import DigitalOutputDevice, Button
from time import sleep

ROWS = [5, 6, 13, 19]
COLS = [12, 16, 20, 21]

KEYS = [
    ['1','2','3','A'],
    ['4','5','6','B'],
    ['7','8','9','C'],
    ['*','0','#','D']
]

def setup_keypad():
    rows = [DigitalOutputDevice(pin, initial_value=True) for pin in ROWS]
    cols = [Button(pin, pull_up=True) for pin in COLS]
    return rows, cols

def read_key(rows, cols):
    for i, row in enumerate(rows):
        row.off()  # pull row LOW
        for j, col in enumerate(cols):
            if not col.is_pressed:
                sleep(0.2)  # debounce
                row.on()
                return KEYS[i][j]
        row.on()
    return None

def main():
    rows, cols = setup_keypad()
    print("Keypad ready...")

    while True:
        key = read_key(rows, cols)
        if key:
            print("Key pressed:", key)

if __name__ == "__main__":
    main()
