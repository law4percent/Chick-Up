import socket
import time
import datetime
import sys

# --- Configuration ---
CHECK_INTERVAL_SECONDS = 5 * 60  # 5 minutes in seconds
TARGET_HOST = "8.8.8.8"        # Google DNS server is reliable
TARGET_PORT = 53               # Standard DNS port
TIMEOUT_SECONDS = 3            # Wait 3 seconds for a connection attempt

def check_external_connection(host, port, timeout):
    """
    Attempts to connect to a reliable external host to verify true internet connectivity.
    """
    try:
        # Create a new socket object (IPv4, TCP stream)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        # Attempt to connect
        s.connect((host, port))
        s.close()
        return True
    except socket.error as e:
        # Catch any network-related errors (timeout, no route to host, etc.)
        return False

def main_loop():
    """
    The main function that runs the check periodically.
    """
    # Initialize connection status flag
    connection_active = False 
    
    print(f"--- Internet Check Service Started ---")
    print(f"Checking every {CHECK_INTERVAL_SECONDS // 60} minutes.")
    
    while True:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if check_external_connection(TARGET_HOST, TARGET_PORT, TIMEOUT_SECONDS):
            # Connection is currently active
            if not connection_active:
                # Only print the "Restored" message once when connection comes up
                print(f"[{current_time}] ✅ Internet connection **RESTORED**. Proceeding with tasks.")
                connection_active = True
            else:
                # Optional: Only print a "still active" message for logging
                # print(f"[{current_time}] Connection still active.")
                pass # Silent when everything is fine
            
            # --- Place your application logic here ---
            # e.g., Call a function that posts data, fetches weather, etc.
            # your_main_task_function()
            # ---------------------------------------

        else:
            # Connection is currently down
            if connection_active:
                # Only print the "LOST" message once when connection drops
                print(f"[{current_time}] ❌ Internet connection **LOST**! Triggering debug/fail mode.")
                # --- Place your error-handling/debugging logic here ---
                # raise ConnectionError("FATAL: Internet connection lost. Debug immediately!")
                connection_active = False

            else:
                # Print a recurring message that the connection is still down
                print(f"[{current_time}] ⚠️ Still no internet connection.")
                
        
        # Wait for the specified interval before checking again
        time.sleep(CHECK_INTERVAL_SECONDS)