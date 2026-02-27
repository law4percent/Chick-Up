import RPi.GPIO as GPIO
import time

# ===== GPIO pins =====
LEFT_TRIG = 25
LEFT_ECHO = 24
RIGHT_TRIG = 7
RIGHT_ECHO = 8

# ===== Setup GPIO =====
def setup_ultrasonics():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(LEFT_TRIG, GPIO.OUT)
    GPIO.setup(LEFT_ECHO, GPIO.IN)
    GPIO.setup(RIGHT_TRIG, GPIO.OUT)
    GPIO.setup(RIGHT_ECHO, GPIO.IN)

    # Ensure TRIG pins are low
    GPIO.output(LEFT_TRIG, False)
    GPIO.output(RIGHT_TRIG, False)
    time.sleep(0.5)  # Let sensors settle


def _measure_distance(TRIG, ECHO):
    """Measure distance for a single sensor in cm."""
    # Send 10µs pulse
    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)

    start = None
    stop = None

    # Wait for ECHO to go HIGH
    timeout = time.time() + 0.04  # 40ms timeout (~6.8m max distance)
    while GPIO.input(ECHO) == 0 and time.time() < timeout:
        start = time.time()

    if start is None:  # No echo received
        return 0.0

    # Wait for ECHO to go LOW
    timeout = time.time() + 0.04
    while GPIO.input(ECHO) == 1 and time.time() < timeout:
        stop = time.time()

    if stop is None:  # Echo never went LOW
        return 0.0

    # Calculate distance
    elapsed = stop - start
    distance = (elapsed * 33112) / 2  # speed of sound in cm/s
    return round(distance, 2)


def read_left_distance() -> float:
    return _measure_distance(LEFT_TRIG, LEFT_ECHO)


def read_right_distance() -> float:
    return _measure_distance(RIGHT_TRIG, RIGHT_ECHO)


if __name__ == "__main__":
    try:
        while True:
            left_distance = _measure_distance(LEFT_TRIG, LEFT_ECHO)
            right_distance = _measure_distance(RIGHT_TRIG, RIGHT_ECHO)

            left_str = f"{left_distance:.1f} cm" if left_distance else "---"
            right_str = f"{right_distance:.1f} cm" if right_distance else "---"

            print(f"Left: {left_str} | Right: {right_str}")
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nExiting...")

    finally:
        GPIO.cleanup()
