from gpiozero import Motor

# LEFT motor
LEFT_IN1 = 17
LEFT_IN2 = 27

# RIGHT motor
RIGHT_IN1 = 22
RIGHT_IN2 = 23

LEFT = Motor(forward=LEFT_IN1, backward=LEFT_IN2)
RIGHT = Motor(forward=RIGHT_IN1, backward=RIGHT_IN2)

def setup_motors() -> list:
    return LEFT, RIGHT

def run_left_motor() -> None:
    LEFT.forward()
    
def run_right_motor() -> None:
    RIGHT.forward()

def stop_left_motor() -> None:
    LEFT.stop()
    
def stop_right_motor() -> None:
    RIGHT.stop()