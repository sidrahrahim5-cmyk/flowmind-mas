# utils/event_store.py
# FlowMind – Shared Event Store
# Thread-safe in-memory store shared between
# SPADE agents and Flask dashboard server

import threading
from datetime import datetime


class EventStore:
    """
    Central shared store for all FlowMind system events.
    SPADE agents write to this store.
    Flask server reads from this store.
    Thread-safe using locks.
    """

    def __init__(self):
        self._lock = threading.Lock()

        # Live sensor readings per equipment
        self.sensor_readings = {}

        # Message feed (last 50 messages)
        self.messages = []

        # Incident log
        self.incidents = []

        # Agent status
        self.agent_status = {
            "fault_detection": {
                "status": "starting", "msg_count": 0
            },
            "diagnostic": {
                "status": "starting", "msg_count": 0
            },
            "people_flow": {
                "status": "starting", "msg_count": 0
            },
            "dispatch": {
                "status": "starting", "msg_count": 0
            },
            "reporting": {
                "status": "starting", "msg_count": 0
            },
        }

        # KPI counters
        self.kpis = {
            "total_incidents":  0,
            "emergencies":      0,
            "scheduled":        0,
            "monitors":         0,
            "downtime_saved":   0,
            "messages_sent":    0,
        }

        # Demand forecasts per equipment
        self.demand_forecasts = {}

    # ── Sensor Updates ────────────────────────────────────────────────
    def update_sensor(self, equipment_id: str, reading: dict,
                      severity: str):
        with self._lock:
            self.sensor_readings[equipment_id] = {
                **reading,
                "severity": severity,
            }

    # ── Message Feed ──────────────────────────────────────────────────
    def add_message(self, text: str, msg_type: str,
                    agent: str = ""):
        with self._lock:
            self.messages.insert(0, {
                "text":      text,
                "type":      msg_type,
                "agent":     agent,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            })
            # Keep last 50 messages only
            self.messages = self.messages[:50]
            self.kpis["messages_sent"] += 1

    # ── Incident Log ──────────────────────────────────────────────────
    def add_incident(self, equipment_id: str, root_cause: str,
                     ttf_hours: float, urgency: str,
                     technician: str, briefing: str,
                     predicted_passengers: int = 0):
        with self._lock:
            self.incidents.insert(0, {
                "equipment_id":          equipment_id,
                "root_cause":            root_cause,
                "ttf_hours":             ttf_hours,
                "urgency":               urgency,
                "technician":            technician,
                "briefing":              briefing,
                "predicted_passengers":  predicted_passengers,
                "timestamp": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            })
            # Keep last 30 incidents
            self.incidents = self.incidents[:30]

            # Update KPIs
            self.kpis["total_incidents"] += 1
            if urgency == "emergency":
                self.kpis["emergencies"]    += 1
                self.kpis["downtime_saved"] += 47
            elif urgency == "scheduled":
                self.kpis["scheduled"]      += 1
                self.kpis["downtime_saved"] += 20
            else:
                self.kpis["monitors"]       += 1

    # ── Agent Status ──────────────────────────────────────────────────
    def update_agent(self, agent_name: str, status: str):
        with self._lock:
            if agent_name in self.agent_status:
                self.agent_status[agent_name]["status"] = status
                self.agent_status[agent_name]["msg_count"] += 1

    # ── Demand Forecast ───────────────────────────────────────────────
    def update_forecast(self, equipment_id: str,
                        passengers: int, risk: str,
                        time_window: str):
        with self._lock:
            self.demand_forecasts[equipment_id] = {
                "passengers":  passengers,
                "risk":        risk,
                "time_window": time_window,
            }

    # ── Snapshot for API ──────────────────────────────────────────────
    def get_snapshot(self) -> dict:
        """Return full system state for dashboard API."""
        with self._lock:
            return {
                "sensor_readings":  dict(self.sensor_readings),
                "messages":         list(self.messages[:30]),
                "incidents":        list(self.incidents[:10]),
                "agent_status":     dict(self.agent_status),
                "kpis":             dict(self.kpis),
                "demand_forecasts": dict(self.demand_forecasts),
                "timestamp": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }


# Global singleton — imported by all agents and Flask server
store = EventStore()