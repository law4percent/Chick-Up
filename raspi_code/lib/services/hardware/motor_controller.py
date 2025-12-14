from gpiozero import Motor

# LEFT motor
LEFT_IN1 = 17
LEFT_IN2 = 27

# RIGHT motor
RIGHT_IN1 = 22
RIGHT_IN2 = 23

def setup_motors() -> list:
    left = Motor(forward=LEFT_IN1, backward=LEFT_IN2)
    right = Motor(forward=RIGHT_IN1, backward=RIGHT_IN2)
    return left, right

def run_left_motor(left) -> None:
    left.forward()
    
def run_right_motor(right) -> None:
    right.forward()

def stop_left_motor(left) -> None:
    left.stop()
    
def stop_right_motor(right) -> None:
    right.stop()