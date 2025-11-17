link_id: str = "ABCDabcd1234567890"

def pair_it(
        device_id: str = "-3GSRmf356dy6GFQSTGIF", 
        testing_mode: bool = False, 
        show_logs: bool = False) -> None:
    
    if testing_mode:
        print("Testing mode enabled: Link ID: {}.")
