import logging
import firebase_admin
from gpiozero import DistanceSensor, Button, DigitalOutputDevice, DigitalInputDevice, PWMOutputDevice
from firebase_admin import db
from RPLCD import CharLCD

logging.basicConfig(
    filename='logs/debug.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def measure_cm(sensor) -> float:
    return sensor.distance * 100


def convert_to_percentage(distance_cm, min_dist=10, max_dist=300) -> float:
    if distance_cm <= min_dist:
        return 100
    if distance_cm >= max_dist:
        return 0
    
    percent = (max_dist - distance_cm) / (max_dist - min_dist) * 100
    return round(percent, 2)

def setup_level_sensors(is_pc_device: bool, feed_level_sensor_data: dict, water_level_sensor_data: dict) -> list:
    if is_pc_device:
        print("Pass, no initializing level sensors...")
        return [None, None]
    
    feed_level_sensor   = DistanceSensor(
                            echo            = feed_level_sensor_data["echo"],
                            trigger         = feed_level_sensor_data["trigger"],
                            max_distance    = feed_level_sensor_data["max_distance"]
                        )
    water_level_sensor  = DistanceSensor(
                            echo            = water_level_sensor_data["echo"],
                            trigger         = water_level_sensor_data["trigger"],
                            max_distance    = water_level_sensor_data["max_distance"]
                        )
    return [feed_level_sensor, water_level_sensor]


def setup_physical_buttons(is_pc_device: bool, feed_physical_button_data: dict, water_physical_button_data: dict) -> list:
    if is_pc_device:
        print("Pass, no initializing physical buttons...")
        return [None, None]
    
    feed_button = Button(feed_physical_button_data["gpio"], pull_up=feed_physical_button_data["pull_up"])
    water_button = Button(water_physical_button_data["gpio"], pull_up=water_physical_button_data["pull_up"])
    return [feed_button, water_button]

def setup_keypad(is_pc_device: bool, keypad_pins_data: dict):
    if is_pc_device:
        print("Pass, no initializing keypad...")
        return None

    row_pins = keypad_pins_data["row_pins"] 
    col_pins = keypad_pins_data["col_pins"]   

    rows = [DigitalOutputDevice(pin, active_high=True, initial_value=True) for pin in row_pins]

    cols = [DigitalInputDevice(pin, pull_up=True) for pin in col_pins]

    key_map = [
        ["D", "#", "0", "*"],
        ["C", "9", "8", "7"],
        ["B", "6", "5", "4"],
        ["A", "3", "2", "1"]
    ]

    return {
        "rows": rows,
        "cols": cols,
        "key_map": key_map
    }

def setup_lcd(is_pc_device: bool, lcd_data: dict):
    """
    lcd_data = {
        "i2c_driver": "PCF8574",   # LCD I2C driver
        "i2c_address": 0x27         # Address detected by i2cdetect
    }
    """
    if is_pc_device:
        print("Pass, no LCD initialized (PC device).")
        return None

    lcd = CharLCD(lcd_data["i2c_driver"], lcd_data["i2c_address"])
    lcd.clear()
    return lcd

def setup_relay(is_pc_device:bool, relay_data: dict):
    if is_pc_device:
        print("Pass, no relay initialized...")
        return None
    
    relay_output = DigitalOutputDevice(
        relay_data["gpio"],
        active_high=relay_data.get("active_high", False),
        initial_value=relay_data.get("initial_value", True)
    )

    return relay_output

def setup_motor_driver(is_pc_device:bool, motor_data: dict):
    if is_pc_device:
        print("Pass, no l289n initialized...")
        return None
    
    in1 = DigitalOutputDevice(motor_data["in1"])
    in2 = DigitalOutputDevice(motor_data["in2"])
    ena = DigitalOutputDevice(motor_data["ena"])

    ena.off()
    in1.off()
    in2.off()

    return {
        "in1": in1,
        "in2": in2,
        "ena": ena
    }

def motor_forward(motor):
    motor["in1"].on()
    motor["in2"].off()
    motor["ena"].on()

def motor_stop(motor):
    motor["ena"].off()
    motor["in1"].off()
    motor["in2"].off()

def lcd_print(lcd, line1="", line2="", line3="", line4=""):
    if lcd is None:
        return  
    lcd.clear()
    lcd.write_string(f"{line1}\n{line2}\n{line3}\n{line4}")

def read_level_sensors_data(feed_level_sensor: any, water_level_sensor: any) -> list:
    feed_dist       = measure_cm(feed_level_sensor)
    water_dist      = measure_cm(water_level_sensor)
    
    feed_level      = convert_to_percentage(feed_dist)
    water_level     = convert_to_percentage(water_dist)
    
    return [feed_level, water_level]


def read_physical_buttons_data(feed_physical_button: any, water_physical_button: any) -> list:
    feed_button_current_status = not feed_physical_button.value
    water_button_current_status = not water_physical_button.value
    return [feed_button_current_status, water_button_current_status]

def read_keypad_data(keypad_pins: any) -> str: 
    rows = keypad_pins["rows"]
    cols = keypad_pins["cols"]
    key_map = keypad_pins["key_map"]

    for r_index, row in enumerate(rows):
        row.off()  

        col_states = [col.value for col in cols]

        if 0 in col_states: 
            c_index = col_states.index(0)
            key_value = key_map[r_index][c_index]

            row.on()
            return key_value

        row.on()

    return None


def read_pins_data(
        feed_physical_button: any,
        water_physical_button: any,
        feed_level_sensor: any,
        water_level_sensor: any,
        keypad_pins: any,
        user_uid: str,
        device_uid: str,
        is_pc_device: bool = False,
        save_logs: bool = False
    ) -> dict | None:
    feed_level = db.reference(f"sensors/{user_uid}/{device_uid}/feedLevel")
    water_level = db.reference(f"sensors/{user_uid}/{device_uid}/waterLevel")

    feed = feed_level.get()
    water = water_level.get()
    if is_pc_device:
        return {
            "feed_current_level": feed,    
            "water_current_level": water,    
            "feed_physical_button_current_state": False,
            "water_physical_button_current_state": False,
            "pressed_key": None
        }
    

    # -------------------------------
    # This handles level sensors
    # -------------------------------
    feed_current_level, water_current_level = read_level_sensors_data(feed_level_sensor=feed_level_sensor, water_level_sensor=water_level_sensor)
    # print(f"{task_name} Current level of feeds  : {feed_current_level}")
    # print(f"{task_name} Current level of water  : {water_current_level}")
     
      
            
    # -------------------------------
    # This handles physical buttons
    # -------------------------------
    feed_physical_button_current_status, water_physical_button_current_status = read_physical_buttons_data(feed_physical_button=feed_physical_button, water_physical_button=water_physical_button)
    # print(f"{task_name} Current physical button status of feed  : {feed_physical_button_current_status}")
    # print(f"{task_name} Current physical button status of water : {water_physical_button_current_status}")

    pressed_key = read_keypad_data(keypad_pins=keypad_pins)

    all_data = {
        "feed_current_level" : feed_current_level,
        "water_current_level": water_current_level,
        "feed_physical_button_current_state": feed_physical_button_current_status,
        "water_physical_button_current_state": water_physical_button_current_status,
        "pressed_key": pressed_key
    }

    return all_data




    
