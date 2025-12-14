import RPi.GPIO as GPIO

# ================= PIN DEFINITIONS =================
LEFT_IN1 = 17
LEFT_IN2 = 27

RIGHT_IN1 = 22
RIGHT_IN2 = 23


# ================= SETUP =================
def setup_motors() -> None:
    GPIO.setmode(GPIO.BCM)

    GPIO.setup(LEFT_IN1, GPIO.OUT)
    GPIO.setup(LEFT_IN2, GPIO.OUT)
    GPIO.setup(RIGHT_IN1, GPIO.OUT)
    GPIO.setup(RIGHT_IN2, GPIO.OUT)

    stop_all_motors()


# ================= LEFT MOTOR =================
def run_left_motor() -> None:
    GPIO.output(LEFT_IN1, GPIO.HIGH)
    GPIO.output(LEFT_IN2, GPIO.LOW)


def stop_left_motor() -> None:
    GPIO.output(LEFT_IN1, GPIO.LOW)
    GPIO.output(LEFT_IN2, GPIO.LOW)


# ================= RIGHT MOTOR =================
def run_right_motor() -> None:
    GPIO.output(RIGHT_IN1, GPIO.HIGH)
    GPIO.output(RIGHT_IN2, GPIO.LOW)


def stop_right_motor() -> None:
    GPIO.output(RIGHT_IN1, GPIO.LOW)
    GPIO.output(RIGHT_IN2, GPIO.LOW)


# ================= SAFETY =================
def stop_all_motors() -> None:
    stop_left_motor()
    stop_right_motor()
