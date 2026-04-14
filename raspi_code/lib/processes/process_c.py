"""
Path: lib/processes/process_c.py
Description:
    Ultrasonic sensor process — reads feed (left) and water (right) HC-SR04
    sensors in a tight dedicated loop and writes results into two shared
    multiprocessing.Value floats that process_b reads every tick.

    Why a separate process?
        process_b runs a 100ms tick loop that also handles keypad scanning,
        Firebase reads, motor logic, and LCD updates. The HC-SR04 median
        filter (5 samples × 30ms apart) takes ~150ms per sensor — longer
        than the entire tick budget. Running both sensors sequentially inside
        the tick loop caused the loop to drift and produced unstable level
        readings because the second sensor fired while the first echo was
        still ringing.

        Moving sensor reads into their own process gives them a dedicated CPU
        core with no competition, allows the median filter to run at full
        fidelity, and lets process_b simply read the latest value from shared
        memory on every tick without blocking.

    IPC — multiprocessing.Value (shared memory):
        Two c_double Values are created in main.py and passed to both
        process_b and process_c:

            shared_feed_level  : c_double — latest feed level  (%)
            shared_water_level : c_double — latest water level (%)

        process_c writes; process_b reads. Value uses a Lock internally so
        reads and writes are atomic — no additional synchronisation needed
        for two simple float updates.

    Sensor loop:
        Each iteration reads left sensor → right sensor using the median
        filter (5 samples). Total cycle time ≈ 300–400ms. The loop runs
        continuously; there is no artificial sleep between cycles so the
        shared values are always as fresh as the hardware allows.

    Shutdown:
        process_c checks status_checker on every iteration. When any other
        process clears status_checker (fatal error) process_c exits cleanly
        and calls GPIO.cleanup().

    Logging contract (same as all service modules in this project):
        process_c logs freely at all levels via get_logger.
        ultrasonic_controller raises exceptions only — no internal logging.
"""

import RPi.GPIO as GPIO

from lib.services.hardware import ultrasonic_controller as distance
from lib.services.logger import get_logger

log = get_logger("process_c.py")


def process_C(**kwargs) -> None:
    args               = kwargs["process_C_args"]
    TASK_NAME          = args["TASK_NAME"]
    status_checker     = args["status_checker"]
    shared_feed_level  = args["shared_feed_level"]   # multiprocessing.Value('d')
    shared_water_level = args["shared_water_level"]  # multiprocessing.Value('d')

    log(details=f"{TASK_NAME} - Running", log_type="info")

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    try:
        distance.setup_ultrasonics()
    except Exception as e:
        log(details=f"{TASK_NAME} - Ultrasonic setup failed: {e}", log_type="error")
        status_checker.clear()
        GPIO.cleanup()
        return

    log(details=f"{TASK_NAME} - Ultrasonic sensors initialized", log_type="info")

    try:
        while True:
            if not status_checker.is_set():
                log(
                    details=f"{TASK_NAME} - status_checker cleared, shutting down",
                    log_type="warning",
                )
                break

            # ── Read feed sensor (left) ───────────────────────────────────
            try:
                feed_cm = distance.read_left_distance()
                feed_pct = _to_percent(feed_cm)
                with shared_feed_level.get_lock():
                    shared_feed_level.value = feed_pct
            except Exception as e:
                log(
                    details=f"{TASK_NAME} - Feed sensor read failed: {e}",
                    log_type="warning",
                )

            # ── Read water sensor (right) ─────────────────────────────────
            try:
                water_cm = distance.read_right_distance()
                water_pct = _to_percent(water_cm)
                with shared_water_level.get_lock():
                    shared_water_level.value = water_pct
            except Exception as e:
                log(
                    details=f"{TASK_NAME} - Water sensor read failed: {e}",
                    log_type="warning",
                )

    except KeyboardInterrupt:
        log(details=f"{TASK_NAME} - KeyboardInterrupt received", log_type="warning")
        status_checker.clear()

    except Exception as e:
        log(details=f"{TASK_NAME} - Unexpected error: {e}", log_type="error")
        status_checker.clear()
        raise

    finally:
        GPIO.cleanup()
        log(details=f"{TASK_NAME} - Process stopped", log_type="info")


# ─────────────────────────── HELPERS ─────────────────────────────────────────

def _to_percent(distance_cm: float, min_dist: int = 10, max_dist: int = 300) -> float:
    """
    Convert HC-SR04 distance (cm) to fill percentage.

    Mirrors the conversion in process_b so both processes use identical
    scaling. Kept here to avoid process_c importing from process_b.
    """
    if distance_cm <= min_dist:
        return 100.0
    if distance_cm >= max_dist:
        return 0.0
    return round((max_dist - distance_cm) / (max_dist - min_dist) * 100, 2)