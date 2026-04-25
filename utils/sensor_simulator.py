# utils/sensor_simulator.py
# FlowMind – Sensor Data Simulator
# In real system this data comes from IoT Sensors
# We are generating  randomly realistic data

import random
import datetime
from config.settings import EQUIPMENT, VIBRATION_THRESHOLD, TEMPERATURE_THRESHOLD, DOOR_CYCLE_THRESHOLD

def get_sensor_reading(equipment_id: str) -> dict:
    """
    Generate simulated sensor reading for equipment unit.
    """

    # 30% chance of anomaly
    inject_fault = random.random() < 0.30

    if inject_fault:
        vibration   = round(random.uniform(7.5, 12.0), 2)   # above threshold
        temperature = round(random.uniform(76.0, 95.0), 2)  # above threshold
        door_cycles = random.randint(960, 1100)              # above threshold
    else:
        vibration   = round(random.uniform(1.0, 6.5), 2)    # normal
        temperature = round(random.uniform(35.0, 72.0), 2)  # normal
        door_cycles = random.randint(100, 900)               # normal

    reading = {
        "equipment_id": equipment_id,
        "timestamp":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "vibration":    vibration,
        "temperature":  temperature,
        "door_cycles":  door_cycles,
        "is_anomaly":   inject_fault,
    }

    return reading


def classify_severity(reading: dict) -> str:
    """
    Classify severity on the basis of Sensor reading.
    Low / Medium / High
    """
    score = 0

    if reading["vibration"]   > VIBRATION_THRESHOLD:   score += 1
    if reading["temperature"] > TEMPERATURE_THRESHOLD: score += 1
    if reading["door_cycles"] > DOOR_CYCLE_THRESHOLD:  score += 1

    if score == 0:
        return "normal"
    elif score == 1:
        return "low"
    elif score == 2:
        return "medium"
    else:
        return "high"


def get_equipment_info(equipment_id: str) -> dict:
    """
    Return the Equipment static info.
    """
    for eq in EQUIPMENT:
        if eq["id"] == equipment_id:
            return eq
    return {"id": equipment_id, "type": "unknown", "location": "unknown"}


def get_all_equipment_ids() -> list:
    """
    Return all equipment IDs list.
    """
    return [eq["id"] for eq in EQUIPMENT]