from firebase_admin import db
import time


# --------------------------------------------------------
# Validate pairing based on realDevices
# --------------------------------------------------------
def check_pairing(device_id: str, input_linked_id: str) -> bool:

    # ---- Check realDevice ----
    real_ref = db.reference(f"devices/realDevices/{device_id}")
    real_data = real_ref.get()

    if real_data is None:
        print(f"[PAIRING] ❌ realDevice '{device_id}' not found.")
        return False

    stored_linked_id = real_data.get("linkedId")
    is_used = real_data.get("isUsedBySomeone")

    if stored_linked_id is None:
        print("[PAIRING] ❌ This device has NO linkedId assigned in Firebase.")
        return False

    # ---- Check if device is already used ----
    if is_used is True:
        print(f"[PAIRING] ❌ Device '{device_id}' is ALREADY PAIRED. Input must match stored linkedId.")
        # Even if already paired, user must input correct linkedId
        # but we still allow pairing if linkedId matches
        # (DO NOT return False here yet)

    # ---- Check if input matches stored linkedId ----
    if input_linked_id != stored_linked_id:
        print(f"[PAIRING] ❌ Input linkedId '{input_linked_id}' DOES NOT MATCH.")
        print(f"[PAIRING] Expected linkedId: {stored_linked_id}")
        return False

    # ---- Check linkedDevices entry ----
    linked_ref = db.reference(f"devices/linkedDevices/{stored_linked_id}")
    linked_data = linked_ref.get()

    if linked_data is None:
        print(f"[PAIRING] ❌ linkedDevices entry for '{stored_linked_id}' does not exist.")
        return False

    print("[PAIRING] ✔ Device and linkedId match!")
    return True


# --------------------------------------------------------
# Write valid pairing to Firebase
# --------------------------------------------------------
def commit_pairing(device_id: str, linked_id: str):

    # Update realDevices
    db.reference(f"devices/realDevices/{device_id}").update({
        "isUsedBySomeone": True
    })

    # Update linkedDevices
    db.reference(f"devices/linkedDevices/{linked_id}").update({
        "isOnline": True,
        "lastOnline": int(time.time())
    })

    print("[PAIRING] 🔒 Device successfully paired!")
    print("[PAIRING] ✔ realDevices updated")
    print("[PAIRING] ✔ linkedDevices updated")


# --------------------------------------------------------
# Loop until correct linkedId is entered
# --------------------------------------------------------
def require_valid_pairing(device_id: str) -> str:
    """
    Keeps requesting linkedId until correct one is entered.
    DOES NOT STOP the program anymore.
    """

    while True:  # KEEP ASKING
        print("Enter your linkedId:")
        typed_linked_id = input("> ").strip()

        # Validate input
        if check_pairing(device_id, typed_linked_id):
            # When valid → commit and return
            commit_pairing(device_id, typed_linked_id)
            print("[PAIRING] Device is now active!\n")
            return typed_linked_id

        # If not valid → loop again
        print("[PAIRING] Incorrect linkedId. Try again...\n")
