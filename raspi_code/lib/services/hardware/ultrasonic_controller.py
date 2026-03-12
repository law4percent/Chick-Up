"""
Ultrasonic Controller
Path: lib/services/hardware/ultrasonic_controller.py

HC-SR04 ultrasonic distance sensors for feed (left) and water (right) level.

Noise reduction:
    Raw HC-SR04 readings spike to 0 or max-range on electrical noise,
    vibration, or foam/surface interference. A single reading per loop tick
    produces false 0% ↔ 100% flips that propagate to motor logic.

    Fix: take SAMPLE_COUNT raw readings per call, discard outliers, return
    the median. Spikes are isolated samples — the median survives them.

Logging contract:
    This is a service module — no logging. Returns 0.0 on read failure.
    Callers (process_b) treat persistent 0.0 as a sensor fault.
"""

import time
import RPi.GPIO as GPIO

# ─────────────────────────── PIN DEFINITIONS ─────────────────────────────────

LEFT_TRIG  = 25   # Feed sensor — trigger
LEFT_ECHO  = 24   # Feed sensor — echo
RIGHT_TRIG = 7    # Water sensor — trigger
RIGHT_ECHO = 8    # Water sensor — echo

# ─────────────────────────── FILTER PARAMETERS ───────────────────────────────

SAMPLE_COUNT     = 5        # Readings per call — odd number keeps median clean
SAMPLE_DELAY     = 0.03     # 30ms between samples — HC-SR04 min cycle is ~25ms
ECHO_TIMEOUT     = 0.04     # 40ms per echo wait — covers ~6.8m max range
VALID_MIN_CM     = 2.0      # Below this = sensor fault / object too close
VALID_MAX_CM     = 400.0    # Above this = no echo / out of range


# ─────────────────────────── SETUP ───────────────────────────────────────────

def setup_ultrasonics() -> None:
    """
    Initialize GPIO pins for both ultrasonic sensors.
    Leaves TRIG pins LOW for 500ms to let sensors settle.
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    GPIO.setup(LEFT_TRIG,  GPIO.OUT)
    GPIO.setup(LEFT_ECHO,  GPIO.IN)
    GPIO.setup(RIGHT_TRIG, GPIO.OUT)
    GPIO.setup(RIGHT_ECHO, GPIO.IN)

    GPIO.output(LEFT_TRIG,  False)
    GPIO.output(RIGHT_TRIG, False)
    time.sleep(0.5)


# ─────────────────────────── RAW MEASUREMENT ─────────────────────────────────

def _measure_once(trig: int, echo: int) -> float:
    """
    Fire one ultrasonic pulse and return the raw distance in cm.

    Returns:
        float: Distance in cm, or 0.0 on timeout / no echo.
    """
    # 10µs trigger pulse
    GPIO.output(trig, True)
    time.sleep(0.00001)
    GPIO.output(trig, False)

    start = None
    stop = None

    # Wait for ECHO to go HIGH
    timeout = time.time() + 0.04  # 40ms timeout (~6.8m max distance)
    while GPIO.input(echo) == 0 and time.time() < timeout:
        start = time.time()

    if start is None:  # No echo received
        return 0.0

    # Wait for ECHO to go LOW
    timeout = time.time() + 0.04
    while GPIO.input(echo) == 1 and time.time() < timeout:
        stop = time.time()

    if stop is None:  # Echo never went LOW
        return 0.0

    # Calculate distance
    elapsed = stop - start
    distance = (elapsed * 33112) / 2  # speed of sound in cm/s
    return round(distance, 2)


# ─────────────────────────── MEDIAN FILTER ───────────────────────────────────

def _median_distance(trig: int, echo: int) -> float:
    """
    Take SAMPLE_COUNT readings, discard out-of-range values, return median.

    Why median and not average:
        Ultrasonic spikes (0 cm or 400+ cm) are isolated outliers caused by
        noise, surface scatter, or missed echoes. Averaging pulls the result
        toward the spike. The median ignores it completely as long as more
        than half the samples are valid.

    Returns:
        float: Stable distance in cm, or 0.0 if no valid samples.
    """
    samples = []

    for _ in range(SAMPLE_COUNT):
        reading = _measure_once(trig, echo)
        if VALID_MIN_CM <= reading <= VALID_MAX_CM:
            samples.append(reading)
        time.sleep(SAMPLE_DELAY)

    if not samples:
        return 0.0

    samples.sort()
    return samples[len(samples) // 2]


# ─────────────────────────── PUBLIC API ──────────────────────────────────────

def read_left_distance() -> float:
    """
    Read feed level sensor (left — GPIO TRIG 25, ECHO 24).

    Returns:
        float: Median distance in cm. 0.0 = sensor fault / no valid reading.
    """
    return _measure_once(LEFT_TRIG, LEFT_ECHO) # _median_distance(LEFT_TRIG, LEFT_ECHO)


def read_right_distance() -> float:
    """
    Read water level sensor (right — GPIO TRIG 7, ECHO 8).

    Returns:
        float: Median distance in cm. 0.0 = sensor fault / no valid reading.
    """
    return _measure_once(RIGHT_TRIG, RIGHT_ECHO) # _median_distance(RIGHT_TRIG, RIGHT_ECHO)