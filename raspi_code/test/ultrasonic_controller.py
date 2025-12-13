from gpiozero import DistanceSensor
from time import sleep

# LEFT sensor
# TRIG → 24
# ECHO → 25

# RIGHT sensor
# TRIG → 8
# ECHO → 7

LEFT_TRIG  = 24
LEFT_ECHO  = 25

RIGHT_TRIG = 8
RIGHT_ECHO = 7

def setup_sensors():
    left = DistanceSensor(echo=LEFT_ECHO, trigger=LEFT_TRIG, max_distance=2)
    right = DistanceSensor(echo=RIGHT_ECHO, trigger=RIGHT_TRIG, max_distance=2)
    return left, right

def get_distances(left, right):
    left_cm = left.distance * 100
    right_cm = right.distance * 100
    return round(left_cm, 2), round(right_cm, 2)

def main():
    left_sensor, right_sensor = setup_sensors()
    print("Ultrasonic sensors ready...")

    while True:
        left_d, right_d = get_distances(left_sensor, right_sensor)
        print(f"Left: {left_d} cm | Right: {right_d} cm")
        sleep(0.5)

if __name__ == "__main__":
    main()
