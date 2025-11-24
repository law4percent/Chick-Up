import logging
from gpiozero import DistanceSensor, Button

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


def read_pins_data(
        feed_physical_button: any,
        water_physical_button: any,
        feed_level_sensor: any,
        water_level_sensor: any,
        is_pc_device: bool = False,
        save_logs: bool = False
    ) -> dict | None:
    
    if is_pc_device:
        return None
    

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

    all_data = {
        "feed_current_level" : feed_current_level,
        "water_current_level": water_current_level,
        "feed_physical_button_current_status": feed_physical_button_current_status,
        "water_physical_button_current_status": water_physical_button_current_status
    }

    return all_data
    
