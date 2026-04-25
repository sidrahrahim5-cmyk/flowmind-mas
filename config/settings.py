# config/settings.py
# FlowMind – Central Configuration

XMPP_SERVER   = "localhost"
XMPP_PASSWORD = "spade"

# Agent JIDs
AGENTS = {
    "fault_detection": f"fault_detection@{XMPP_SERVER}",
    "diagnostic":      f"diagnostic@{XMPP_SERVER}",
    "people_flow":     f"people_flow@{XMPP_SERVER}",
    "dispatch":        f"dispatch@{XMPP_SERVER}",
    "reporting":       f"reporting@{XMPP_SERVER}",
}

# Simulation timing
SENSOR_CHECK_INTERVAL = 5
FORECAST_INTERVAL     = 8
REPORT_INTERVAL       = 40

# Fault thresholds
VIBRATION_THRESHOLD   = 7.0
TEMPERATURE_THRESHOLD = 75.0
DOOR_CYCLE_THRESHOLD  = 950

# Equipment list
EQUIPMENT = [
    {"id": "ELV-01", "type": "elevator",  "location": "Helsinki Tower, Floor 1-22"},
    {"id": "ELV-04", "type": "elevator",  "location": "Helsinki Tower, Floor 1-22"},
    {"id": "ESC-A",  "type": "escalator", "location": "Mall, North Wing"},
    {"id": "ESC-B",  "type": "escalator", "location": "Mall, South Wing"},
]