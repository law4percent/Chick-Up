import os

def path_existence_check_point(PATH: str, SOURCE: str) -> dict:
    if not os.path.exists(PATH):
        return {
            "status"    : "error", 
            "message"   : f"{PATH} does not exist. Source: {SOURCE}"
        }
    return {"status": "success"}


def file_existence_check_point(PATH: str, SOURCE: str) -> dict:
    if not os.path.isfile(PATH):
        return {
            "status"    : "error", 
            "message"   : f"{PATH} file does not exist. Source: {SOURCE}"
        }
    return {"status": "success"}


def path_exist_else_create_check_point(*paths) -> None:
    for path in paths:
        if not os.path.exists(path):
            os.makedirs(path)
            
            
def join_path_with_os_adaptability(TARGET_PATH: str, FILE_NAME: str, SOURCE: str, create_one: bool = True) -> str:
    check_point_result = path_existence_check_point(TARGET_PATH, SOURCE)
    if check_point_result["status"] == "error" and create_one:
        path_exist_else_create_check_point(TARGET_PATH)
        
    return os.path.join(TARGET_PATH, FILE_NAME)