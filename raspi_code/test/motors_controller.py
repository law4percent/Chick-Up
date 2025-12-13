from gpiozero import Motor
from time import sleep

# LEFT motor
# IN1 → 17
# IN2 → 27

# RIGHT motor
# IN3 → 22
# IN4 → 23

# LEFT motor
LEFT_IN1 = 17
LEFT_IN2 = 27

# RIGHT motor
RIGHT_IN1 = 22
RIGHT_IN2 = 23

def setup_motors():
    left = Motor(forward=LEFT_IN1, backward=LEFT_IN2)
    right = Motor(forward=RIGHT_IN1, backward=RIGHT_IN2)
    return left, right

def forward(left, right):
    left.forward()
    right.forward()

def backward(left, right):
    left.backward()
    right.backward()

def turn_left(left, right):
    left.stop()
    right.forward()

def turn_right(left, right):
    left.forward()
    right.stop()

def stop(left, right):
    left.stop()
    right.stop()

def main():
    left, right = setup_motors()

    forward(left, right)
    sleep(2)

    turn_left(left, right)
    sleep(1)

    turn_right(left, right)
    sleep(1)

    backward(left, right)
    sleep(2)

    stop(left, right)

if __name__ == "__main__":
    main()
