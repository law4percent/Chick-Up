"""
Docstring for raspi_code.lib.services.hardware.motor_controller
Path: raspi_code/lib/services/hardware/motor_controller.py
Description: Motor controller for feed and water dispensing/refilling.
             Controls relay modules connected to GPIO pins.
"""

import RPi.GPIO as GPIO
import logging

logger = logging.getLogger(__name__)

# ================= PIN DEFINITIONS =================
FEED_MOTOR = 17   # GPIO 17 - Feed dispenser relay
WATER_MOTOR = 27  # GPIO 27 - Water pump relay

# Relay logic (change these if your relay module is active LOW)
ON = GPIO.HIGH    # Set to GPIO.LOW if relay is active LOW
OFF = GPIO.LOW    # Set to GPIO.HIGH if relay is active LOW


# ================= SETUP =================
def setup_motors() -> None:
    """
    Initialize GPIO pins for motor control.
    Sets both motors to OFF state.
    """
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        GPIO.setup(FEED_MOTOR, GPIO.OUT)
        GPIO.setup(WATER_MOTOR, GPIO.OUT)
        
        # Ensure all motors start in OFF state
        stop_all_motors()
        
        logger.info("Motor controller initialized successfully")
    except Exception as e:
        logger.error(f"Error setting up motors: {e}")
        raise


# ================= FEED MOTOR CONTROL =================
def start_feed_motor() -> None:
    """Start the feed dispenser motor."""
    try:
        GPIO.output(FEED_MOTOR, ON)
        logger.debug("Feed motor started")
    except Exception as e:
        logger.error(f"Error starting feed motor: {e}")


def stop_feed_motor() -> None:
    """Stop the feed dispenser motor."""
    try:
        GPIO.output(FEED_MOTOR, OFF)
        logger.debug("Feed motor stopped")
    except Exception as e:
        logger.error(f"Error stopping feed motor: {e}")


def on_feed_motor() -> None:
    """Alias for start_feed_motor (for backwards compatibility)."""
    start_feed_motor()


def off_feed_motor() -> None:
    """Alias for stop_feed_motor (for backwards compatibility)."""
    stop_feed_motor()


# ================= WATER MOTOR CONTROL =================
def start_water_motor() -> None:
    """Start the water pump motor."""
    try:
        GPIO.output(WATER_MOTOR, ON)
        logger.debug("Water motor started")
    except Exception as e:
        logger.error(f"Error starting water motor: {e}")


def stop_water_motor() -> None:
    """Stop the water pump motor."""
    try:
        GPIO.output(WATER_MOTOR, OFF)
        logger.debug("Water motor stopped")
    except Exception as e:
        logger.error(f"Error stopping water motor: {e}")


def on_water_motor() -> None:
    """Alias for start_water_motor (for backwards compatibility)."""
    start_water_motor()


def off_water_motor() -> None:
    """Alias for stop_water_motor (for backwards compatibility)."""
    stop_water_motor()


# ================= UTILITY FUNCTIONS =================
def stop_all_motors() -> None:
    """
    Emergency stop - turns off all motors.
    Should be called on shutdown or error conditions.
    """
    try:
        GPIO.output(FEED_MOTOR, OFF)
        GPIO.output(WATER_MOTOR, OFF)
        logger.info("All motors stopped")
    except Exception as e:
        logger.error(f"Error stopping all motors: {e}")


def get_feed_motor_state() -> bool:
    """
    Get current state of feed motor.
    Returns True if ON, False if OFF.
    """
    try:
        return GPIO.input(FEED_MOTOR) == ON
    except Exception as e:
        logger.error(f"Error reading feed motor state: {e}")
        return False


def get_water_motor_state() -> bool:
    """
    Get current state of water motor.
    Returns True if ON, False if OFF.
    """
    try:
        return GPIO.input(WATER_MOTOR) == ON
    except Exception as e:
        logger.error(f"Error reading water motor state: {e}")
        return False


def cleanup() -> None:
    """
    Cleanup motor controller.
    Stops all motors and releases GPIO resources.
    """
    try:
        stop_all_motors()
        logger.info("Motor controller cleaned up")
    except Exception as e:
        logger.error(f"Error during motor cleanup: {e}")


# ================= SAFETY FEATURES =================
def emergency_stop() -> None:
    """
    Emergency stop function.
    Immediately stops all motors and logs the event.
    """
    logger.warning("EMERGENCY STOP activated!")
    stop_all_motors()


# For testing purposes
if __name__ == "__main__":
    import time
    
    print("Testing motor controller...")
    
    try:
        setup_motors()
        
        print("Testing feed motor...")
        start_feed_motor()
        time.sleep(2)
        stop_feed_motor()
        
        print("Testing water motor...")
        start_water_motor()
        time.sleep(2)
        stop_water_motor()
        
        print("Test complete!")
        
    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        stop_all_motors()
        GPIO.cleanup()