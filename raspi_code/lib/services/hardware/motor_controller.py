"""
Motor Controller Module
Path: lib/services/hardware/motor_controller.py
Description:
    Controls feed and water motor relays via GPIO.

Logging contract:
    This is a service module — it raises exceptions only.
    All logging is handled by the calling process.
"""

import RPi.GPIO as GPIO


# ─────────────────────────── EXCEPTIONS ──────────────────────────────────────

class MotorError(Exception):
    """Base exception for motor controller errors."""
    pass

class MotorSetupError(MotorError):
    """Raised when GPIO motor setup fails."""
    pass

class MotorControlError(MotorError):
    """Raised when a motor start/stop operation fails."""
    pass


# ─────────────────────────── PIN DEFINITIONS ─────────────────────────────────

FEED_MOTOR  = 17   # GPIO 17 — Feed dispenser relay
WATER_MOTOR = 27   # GPIO 27 — Water pump relay

# Relay logic — change if your relay module is active LOW
ON  = GPIO.LOW    # Set to GPIO.LOW  if relay is active LOW
OFF = GPIO.HIGH     # Set to GPIO.HIGH if relay is active LOW


# ─────────────────────────── SETUP ───────────────────────────────────────────

def setup_motors() -> None:
    """
    Initialize GPIO pins for motor control.
    Sets both motors to OFF state on startup.

    Raises:
        MotorSetupError: If GPIO setup fails.
    """
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(FEED_MOTOR,  GPIO.OUT)
        GPIO.setup(WATER_MOTOR, GPIO.OUT)
        stop_all_motors()
    except Exception as e:
        raise MotorSetupError(
            f"Failed to setup motors: {e}. Source: {__name__}"
        ) from e


# ─────────────────────────── FEED MOTOR ──────────────────────────────────────

def start_feed_motor() -> None:
    """
    Start the feed dispenser motor.

    Raises:
        MotorControlError: If GPIO output fails.
    """
    try:
        GPIO.output(FEED_MOTOR, ON)
    except Exception as e:
        raise MotorControlError(
            f"Failed to start feed motor: {e}. Source: {__name__}"
        ) from e


def stop_feed_motor() -> None:
    """
    Stop the feed dispenser motor.

    Raises:
        MotorControlError: If GPIO output fails.
    """
    try:
        GPIO.output(FEED_MOTOR, OFF)
    except Exception as e:
        raise MotorControlError(
            f"Failed to stop feed motor: {e}. Source: {__name__}"
        ) from e


# ─────────────────────────── WATER MOTOR ─────────────────────────────────────

def start_water_motor() -> None:
    """
    Start the water pump motor.

    Raises:
        MotorControlError: If GPIO output fails.
    """
    try:
        GPIO.output(WATER_MOTOR, ON)
    except Exception as e:
        raise MotorControlError(
            f"Failed to start water motor: {e}. Source: {__name__}"
        ) from e


def stop_water_motor() -> None:
    """
    Stop the water pump motor.

    Raises:
        MotorControlError: If GPIO output fails.
    """
    try:
        GPIO.output(WATER_MOTOR, OFF)
    except Exception as e:
        raise MotorControlError(
            f"Failed to stop water motor: {e}. Source: {__name__}"
        ) from e


# ─────────────────────────── UTILITY ─────────────────────────────────────────

def stop_all_motors() -> None:
    """
    Emergency stop — turns off all motors immediately.
    Called on shutdown or error conditions.

    Raises:
        MotorControlError: If GPIO output fails.
    """
    try:
        GPIO.output(FEED_MOTOR,  OFF)
        GPIO.output(WATER_MOTOR, OFF)
    except Exception as e:
        raise MotorControlError(
            f"Failed to stop all motors: {e}. Source: {__name__}"
        ) from e


def get_feed_motor_state() -> bool:
    """
    Get current state of the feed motor.

    Returns:
        True if ON, False if OFF or on read failure.
    """
    try:
        return GPIO.input(FEED_MOTOR) == ON
    except Exception:
        return False


def get_water_motor_state() -> bool:
    """
    Get current state of the water motor.

    Returns:
        True if ON, False if OFF or on read failure.
    """
    try:
        return GPIO.input(WATER_MOTOR) == ON
    except Exception:
        return False


def cleanup() -> None:
    """
    Stop all motors. GPIO cleanup is handled by the calling process
    via GPIO.cleanup() — not done here to avoid releasing shared pins.

    Raises:
        MotorControlError: If stop_all_motors fails.
    """
    stop_all_motors()