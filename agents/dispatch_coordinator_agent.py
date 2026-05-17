# agents/dispatch_coordinator_agent.py
# FlowMind – Dispatch Coordinator Agent (BDI-enhanced)
# Now uses BeliefBase, GoalManager, and PlanLibrary for reasoning

import json
import random
import datetime
import spade
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from config.settings import AGENTS
from utils.message_templates import make_dispatch_decision_msg
from utils.event_store import store
from agents.bdi_engine import BeliefBase, GoalManager, Goal, PlanLibrary


class DispatchCoordinatorAgent(spade.agent.Agent):

    TECHNICIANS = [
        {"name": "Mikael Virtanen", "location": "Helsinki CBD",
         "speciality": "elevator"},
        {"name": "Sanna Korhonen",  "location": "Mall District",
         "speciality": "escalator"},
        {"name": "Juhani Makinen",  "location": "North Helsinki",
         "speciality": "elevator"},
        {"name": "Aino Nieminen",   "location": "South Helsinki",
         "speciality": "general"},
    ]

    def __init__(self, jid, password):
        super().__init__(jid, password)

        # ── BDI Components ─────────────────────────────────────
        self.beliefs = BeliefBase()
        self.goals   = GoalManager()

        # Raw message stores (unchanged from before)
        self.diagnostic_reports = {}
        self.demand_forecasts   = {}
        self.fault_alerts       = {}

    # ──────────────────────────────────────────────────────────
    # BEHAVIOUR 1: Receive Fault Alert from FaultDetectionAgent
    # Updates beliefs: severity, timestamp
    # Adds goals: DISPATCH_TECHNICIAN, RESTORE_SERVICE
    # ──────────────────────────────────────────────────────────
    class ReceiveFaultAlertBehaviour(CyclicBehaviour):

        async def run(self):
            msg = await self.receive(timeout=10)
            if msg is None:
                return
            try:
                data = json.loads(msg.body)
                if data.get("msg_type") != "fault_alert":
                    return

                eq_id    = data["equipment_id"]
                severity = data["severity"]

                print(f"\n[Dispatch] 📥 Fault alert — "
                      f"{eq_id} | {severity.upper()}")

                store.update_agent("dispatch", "alert received")
                store.add_message(
                    f"📥 Fault alert received — "
                    f"{eq_id} | Severity: {severity.upper()}",
                    "dispatch", "dispatch"
                )

                # ── Update Beliefs ─────────────────────────────
                self.agent.beliefs.update(eq_id, "severity",  severity)
                self.agent.beliefs.update(eq_id, "fault_time",
                    data.get("timestamp", "unknown"))

                # ── Add Goals ──────────────────────────────────
                self.agent.goals.add_goal(
                    eq_id, Goal.DISPATCH_TECHNICIAN,
                    "DISPATCH_TECHNICIAN",
                    f"Fault detected — severity {severity}"
                )
                self.agent.goals.add_goal(
                    eq_id, Goal.RESTORE_SERVICE,
                    "RESTORE_SERVICE",
                    "Equipment failure must be resolved"
                )

                self.agent.fault_alerts[eq_id] = data
                await self.agent._try_dispatch(eq_id)

            except Exception as e:
                print(f"[Dispatch] ❌ Fault alert error: {e}")

    # ──────────────────────────────────────────────────────────
    # BEHAVIOUR 2: Receive Diagnostic Report from DiagnosticAgent
    # Updates beliefs: root_cause, ttf_hours, action
    # ──────────────────────────────────────────────────────────
    class ReceiveDiagnosticReportBehaviour(CyclicBehaviour):

        async def run(self):
            msg = await self.receive(timeout=10)
            if msg is None:
                return
            try:
                data = json.loads(msg.body)
                if data.get("msg_type") != "diagnostic_report":
                    return

                eq_id = data["equipment_id"]

                print(f"\n[Dispatch] 📥 Diagnostic report — {eq_id}")
                print(f"  Root Cause: {data['root_cause']}")
                print(f"  TTF       : {data['ttf_hours']}h")

                store.update_agent("dispatch", "report received")
                store.add_message(
                    f"📥 Diagnostic report — {eq_id} | "
                    f"TTF: {data['ttf_hours']}h | "
                    f"{data['action'].upper()}",
                    "dispatch", "dispatch"
                )

                # ── Update Beliefs ─────────────────────────────
                self.agent.beliefs.update(eq_id, "root_cause", data["root_cause"])
                self.agent.beliefs.update(eq_id, "ttf_hours",  data["ttf_hours"])
                self.agent.beliefs.update(eq_id, "action",     data["action"])

                self.agent.diagnostic_reports[eq_id] = data
                await self.agent._try_dispatch(eq_id)

            except Exception as e:
                print(f"[Dispatch] ❌ Diagnostic error: {e}")

    # ──────────────────────────────────────────────────────────
    # BEHAVIOUR 3: Receive Demand Forecast from PeopleFlowAgent
    # Updates beliefs: passengers, risk_level, is_rush_hour
    # Adds conflicting goal if rush hour: MINIMIZE_DISRUPTION
    # ──────────────────────────────────────────────────────────
    class ReceiveDemandForecastBehaviour(CyclicBehaviour):

        async def run(self):
            msg = await self.receive(timeout=10)
            if msg is None:
                return
            try:
                data = json.loads(msg.body)
                if data.get("msg_type") != "demand_forecast":
                    return

                eq_id     = data["equipment_id"]
                passengers = data["predicted_passengers"]
                risk      = data["risk_level"]

                print(f"[Dispatch] 📥 Forecast — {eq_id} | "
                      f"{passengers} pax | Risk: {risk.upper()}")

                # ── Update Beliefs ─────────────────────────────
                self.agent.beliefs.update(eq_id, "passengers",  passengers)
                self.agent.beliefs.update(eq_id, "risk_level",  risk)

                # Determine if this is rush hour from time window
                is_rush = passengers >= 200
                self.agent.beliefs.update(eq_id, "is_rush_hour", is_rush)

                # ── Add Conflicting Goal if Rush Hour ──────────
                # This is what enables Scenario 2 conflict detection
                if is_rush:
                    self.agent.goals.add_goal(
                        eq_id, Goal.MINIMIZE_DISRUPTION,
                        "MINIMIZE_DISRUPTION",
                        f"Rush hour — {passengers} passengers at risk"
                    )
                    self.agent.goals.add_goal(
                        eq_id, Goal.PASSENGER_SAFETY,
                        "PASSENGER_SAFETY",
                        "Passenger safety must be considered in all decisions"
                    )

                self.agent.demand_forecasts[eq_id] = data
                await self.agent._try_dispatch(eq_id)

            except Exception as e:
                print(f"[Dispatch] ❌ Forecast error: {e}")

    # ──────────────────────────────────────────────────────────
    # CORE: Try Dispatch — runs after every message
    # Waits until both fault alert AND diagnostic are available.
    # Then invokes BDI reasoning to make dispatch decision.
    # ──────────────────────────────────────────────────────────
    async def _try_dispatch(self, equipment_id: str):
        has_alert      = equipment_id in self.fault_alerts
        has_diagnostic = equipment_id in self.diagnostic_reports

        if not (has_alert and has_diagnostic):
            return  # Not enough information yet — wait

        # ── Print current belief and goal state ───────────────
        print(f"\n{'='*55}")
        print(f"  [BDI] Reasoning for {equipment_id}")
        print(self.beliefs.summary(equipment_id))
        print(self.goals.summary(equipment_id))
        print(f"{'='*55}")

        # ── BDI: Select Plan ──────────────────────────────────
        decision = PlanLibrary.select_plan(
            equipment_id, self.beliefs, self.goals
        )

        urgency   = decision["urgency"]
        reasoning = decision["reasoning"]
        scenario  = decision["scenario"]
        conflict  = decision["conflict"]

        # ── Select technician ─────────────────────────────────
        technician = self._select_technician(equipment_id)

        # ── Build briefing ────────────────────────────────────
        diagnostic = self.diagnostic_reports[equipment_id]
        demand     = self.demand_forecasts.get(equipment_id, None)
        pax        = demand["predicted_passengers"] if demand else 0

        briefing = (
            f"[{scenario}] "
            f"UNIT {equipment_id} | {urgency.upper()} | "
            f"{diagnostic['root_cause']} | "
            f"TTF: {diagnostic['ttf_hours']}h | "
            f"Load: {pax} passengers | "
            f"Conflict: {conflict}"
        )

        print(f"\n[Dispatch] 🚨 DISPATCH DECISION — {equipment_id}")
        print(f"  Scenario  : {scenario}")
        print(f"  Urgency   : {urgency.upper()}")
        print(f"  Technician: {technician['name']}")
        print(f"  Conflict  : {conflict}")
        print(f"  Reasoning :\n    {reasoning}")

        store.update_agent("dispatch", f"{scenario} → {urgency}")
        store.add_message(
            f"🚨 [{scenario}] DISPATCH — {equipment_id} | "
            f"{urgency.upper()} | Conflict:{conflict} | "
            f"→ {technician['name']}",
            "dispatch", "dispatch"
        )

        # ── Log incident ──────────────────────────────────────
        store.add_incident(
            equipment_id=equipment_id,
            root_cause=diagnostic["root_cause"],
            ttf_hours=diagnostic["ttf_hours"],
            urgency=urgency,
            technician=technician["name"],
            briefing=briefing,
            predicted_passengers=pax,
        )

        # ── Send work order to Reporting Agent ────────────────
        msg = make_dispatch_decision_msg(
            to=AGENTS["reporting"],
            equipment_id=equipment_id,
            technician=technician["name"],
            urgency=urgency,
            briefing=briefing,
            root_cause=diagnostic["root_cause"],
            ttf_hours=diagnostic["ttf_hours"],
        )
        await self.behaviours[0].send(msg)

        store.add_message(
            f"📤 Work order → Reporting Agent ({equipment_id})",
            "dispatch", "dispatch"
        )
        print(f"[Dispatch] 📤 Work order → Reporting ({equipment_id})")

        # ── Clear processed data and BDI state ────────────────
        self.fault_alerts.pop(equipment_id, None)
        self.diagnostic_reports.pop(equipment_id, None)
        self.beliefs.clear(equipment_id)
        self.goals.clear(equipment_id)

    # ──────────────────────────────────────────────────────────
    # HELPER: Select technician by equipment type
    # ──────────────────────────────────────────────────────────
    def _select_technician(self, equipment_id):
        eq_type     = "elevator" if "ELV" in equipment_id \
                      else "escalator"
        specialists = [
            t for t in self.TECHNICIANS
            if t["speciality"] == eq_type
        ]
        return random.choice(specialists) if specialists \
               else random.choice(self.TECHNICIANS)

    # ──────────────────────────────────────────────────────────
    # SETUP
    # ──────────────────────────────────────────────────────────
    async def setup(self):
        print("\n" + "="*55)
        print("  [Dispatch] 🤖 Dispatch Coordinator Agent STARTED")
        print("  BDI Engine: BeliefBase + GoalManager + PlanLibrary")
        print("="*55 + "\n")

        store.update_agent("dispatch", "standby")
        store.add_message(
            "🤖 Dispatch Coordinator started — BDI reasoning active",
            "system", "dispatch"
        )

        t1 = Template()
        t1.set_metadata("ontology", "fault-alert")
        b1 = self.ReceiveFaultAlertBehaviour()
        self.add_behaviour(b1, t1)

        t2 = Template()
        t2.set_metadata("ontology", "diagnostic-report")
        b2 = self.ReceiveDiagnosticReportBehaviour()
        self.add_behaviour(b2, t2)

        t3 = Template()
        t3.set_metadata("ontology", "demand-forecast")
        b3 = self.ReceiveDemandForecastBehaviour()
        self.add_behaviour(b3, t3)