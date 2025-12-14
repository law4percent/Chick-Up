from gpiozero import Motor

# ================= PIN DEFINITIONS =================
LEFT_IN1 = 17
LEFT_IN2 = 27

RIGHT_IN1 = 22
RIGHT_IN2 = 23

# ================= MOTOR OBJECTS =================
LEFT_MOTOR = Motor(forward=LEFT_IN1, backward=LEFT_IN2)
RIGHT_MOTOR = Motor(forward=RIGHT_IN1, backward=RIGHT_IN2)

# ================= LEFT MOTOR =================
def run_left_motor() -> None:
    if not LEFT_MOTOR.is_active:
        LEFT_MOTOR.forward()

def stop_left_motor() -> None:
    LEFT_MOTOR.stop()

# ================= RIGHT MOTOR =================
def run_right_motor() -> None:
    if not RIGHT_MOTOR.is_active:
        RIGHT_MOTOR.forward()

def stop_right_motor() -> None:
    RIGHT_MOTOR.stop()

# ================= SAFETY =================
def stop_all_motors() -> None:
    LEFT_MOTOR.stop()
    RIGHT_MOTOR.stop()
