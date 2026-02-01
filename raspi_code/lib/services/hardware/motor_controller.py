import RPi.GPIO as GPIO

# ================= PIN DEFINITIONS =================
FEED_MOTOR = 17
WATER_MOTOR = 27

ON = GPIO.HIGH
OFF = GPIO.LOW

# ================= SETUP =================
def setup_motors() -> None:
    GPIO.setmode(GPIO.BCM)

    GPIO.setup(FEED_MOTOR, GPIO.OUT)
    GPIO.setup(WATER_MOTOR, GPIO.OUT)

    stop_all_motors()


def on_feed_motor() -> None:
    GPIO.output(FEED_MOTOR, ON)
    
def off_feed_motor() -> None:
    GPIO.output(FEED_MOTOR, OFF)
    
def on_water_motor() -> None:
    GPIO.output(WATER_MOTOR, ON)
    
def off_water_motor() -> None:
    GPIO.output(WATER_MOTOR, OFF)

def stop_all_motors() -> None:
    GPIO.output(FEED_MOTOR, OFF)
    GPIO.output(WATER_MOTOR, OFF)