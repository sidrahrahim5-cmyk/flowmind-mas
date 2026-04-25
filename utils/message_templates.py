# utils/message_templates.py
# FlowMind – Message Templates
# standardized message format for all agents

import json
from spade.message import Message


# ─────────────────────────────────────────
# FAULT DETECTION → DIAGNOSTIC
# ─────────────────────────────────────────
def make_fault_signature_msg(to: str, reading: dict, severity: str) -> Message:
    """
    Fault Detection Agent → Diagnostic Agent
    Sent after Anomaly detection
    """
    msg = Message(to=to)
    msg.set_metadata("performative", "inform")
    msg.set_metadata("ontology",     "fault-detection")
    msg.body = json.dumps({
        "msg_type":     "fault_signature",
        "equipment_id": reading["equipment_id"],
        "timestamp":    reading["timestamp"],
        "vibration":    reading["vibration"],
        "temperature":  reading["temperature"],
        "door_cycles":  reading["door_cycles"],
        "severity":     severity,
    })
    return msg


# ─────────────────────────────────────────
# FAULT DETECTION → DISPATCH
# ─────────────────────────────────────────
def make_fault_alert_msg(to: str, reading: dict, severity: str) -> Message:
    """
    Fault Detection Agent → Dispatch Coordinator
    Initial alert — notify dispatch directly for faster response
    """
    msg = Message(to=to)
    msg.set_metadata("performative", "inform")
    msg.set_metadata("ontology",     "fault-alert")
    msg.body = json.dumps({
        "msg_type":     "fault_alert",
        "equipment_id": reading["equipment_id"],
        "timestamp":    reading["timestamp"],
        "severity":     severity,
    })
    return msg


# ─────────────────────────────────────────
# DIAGNOSTIC → DISPATCH
# ─────────────────────────────────────────
def make_diagnostic_report_msg(to: str, equipment_id: str,
                                root_cause: str, ttf_hours: float,
                                action: str, severity: str) -> Message:
    """
    Diagnostic Agent → Dispatch Coordinator
    Root cause analysis and time-to-failure estimation report
    """
    msg = Message(to=to)
    msg.set_metadata("performative", "inform")
    msg.set_metadata("ontology",     "diagnostic-report")
    msg.body = json.dumps({
        "msg_type":     "diagnostic_report",
        "equipment_id": equipment_id,
        "root_cause":   root_cause,
        "ttf_hours":    ttf_hours,
        "action":       action,
        "severity":     severity,
    })
    return msg


# ─────────────────────────────────────────
# PEOPLE FLOW → DISPATCH
# ─────────────────────────────────────────
def make_demand_forecast_msg(to: str, equipment_id: str,
                              predicted_passengers: int,
                              time_window: str, risk_level: str) -> Message:
    """
    People Flow Predictor → Dispatch Coordinator
    Passenger demand forecast
    """
    msg = Message(to=to)
    msg.set_metadata("performative", "inform")
    msg.set_metadata("ontology",     "demand-forecast")
    msg.body = json.dumps({
        "msg_type":            "demand_forecast",
        "equipment_id":        equipment_id,
        "predicted_passengers": predicted_passengers,
        "time_window":         time_window,
        "risk_level":          risk_level,
    })
    return msg


# ─────────────────────────────────────────
# DISPATCH → REPORTING
# ─────────────────────────────────────────
def make_dispatch_decision_msg(to: str, equipment_id: str, technician: str,
                                urgency: str, briefing: str,
                                root_cause: str, ttf_hours: float) -> Message:
    """
    Dispatch Coordinator → Reporting Agent
    Work order issued — notify reporting for record-keeping and future analysis"""
    msg = Message(to=to)
    msg.set_metadata("performative", "inform")
    msg.set_metadata("ontology",     "dispatch-decision")
    msg.body = json.dumps({
        "msg_type":     "dispatch_decision",
        "equipment_id": equipment_id,
        "technician":   technician,
        "urgency":      urgency,
        "briefing":     briefing,
        "root_cause":   root_cause,
        "ttf_hours":    ttf_hours,
    })
    return msg