from firebase_admin import db

def read_pins_data(
    dispense_feed_pin: int,
    water_refill_pin: int,
    keypad_pins: dict,
    df_level_sensor_pins: dict,
    wf_level_sensor_pins: dict
):
    df_system_button_status = False
    wr_system_button_status = False
    keypad_data = ""
    sensors_data = {"df": {}, "wf": {}}

    return (
        df_system_button_status,
        wr_system_button_status,
        keypad_data,
        sensors_data
    )
