# agents/dispatch_coordinator_agent.py
import json
import random
import spade
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from config.settings import AGENTS
from utils.message_templates import make_dispatch_decision_msg
from utils.event_store import store


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
        self.diagnostic_reports = {}
        self.demand_forecasts   = {}
        self.fault_alerts       = {}

    class ReceiveFaultAlertBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg is None:
                return
            try:
                data = json.loads(msg.body)
                if data.get("msg_type") != "fault_alert":
                    return

                eq_id = data["equipment_id"]
                print(f"\n[Dispatch] 📥 Fault alert — "
                      f"{eq_id} | {data['severity'].upper()}")

                store.update_agent("dispatch", "alert received")
                store.add_message(
                    f"📥 Fault alert received — "
                    f"{eq_id} | Severity: {data['severity'].upper()}",
                    "dispatch", "dispatch"
                )
                self.agent.fault_alerts[eq_id] = data
                await self.agent._try_dispatch(eq_id)

            except Exception as e:
                print(f"[Dispatch] ❌ Fault alert error: {e}")

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
                self.agent.diagnostic_reports[eq_id] = data
                await self.agent._try_dispatch(eq_id)

            except Exception as e:
                print(f"[Dispatch] ❌ Diagnostic error: {e}")

    class ReceiveDemandForecastBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if msg is None:
                return
            try:
                data = json.loads(msg.body)
                if data.get("msg_type") != "demand_forecast":
                    return

                eq_id = data["equipment_id"]
                print(f"[Dispatch] 📥 Forecast — {eq_id} | "
                      f"{data['predicted_passengers']} pax")

                self.agent.demand_forecasts[eq_id] = data
                await self.agent._try_dispatch(eq_id)

            except Exception as e:
                print(f"[Dispatch] ❌ Forecast error: {e}")

    async def _try_dispatch(self, equipment_id: str):
        has_alert      = equipment_id in self.fault_alerts
        has_diagnostic = equipment_id in self.diagnostic_reports

        if not (has_alert and has_diagnostic):
            return

        alert      = self.fault_alerts[equipment_id]
        diagnostic = self.diagnostic_reports[equipment_id]
        demand     = self.demand_forecasts.get(equipment_id, None)

        # Autonomous decisions
        urgency    = self._classify_urgency(diagnostic, demand)
        technician = self._select_technician(equipment_id)
        briefing   = self._generate_briefing(
            equipment_id, diagnostic, demand, urgency
        )

        pax = demand["predicted_passengers"] if demand else 0

        print(f"\n[Dispatch] 🚨 DISPATCH — {equipment_id}")
        print(f"  Urgency   : {urgency.upper()}")
        print(f"  Technician: {technician['name']}")

        store.update_agent("dispatch", f"dispatching → {urgency}")
        store.add_message(
            f"🚨 DISPATCH DECISION — {equipment_id} | "
            f"{urgency.upper()} | → {technician['name']}",
            "dispatch", "dispatch"
        )

        # Add to incident log in event store
        store.add_incident(
            equipment_id=equipment_id,
            root_cause=diagnostic["root_cause"],
            ttf_hours=diagnostic["ttf_hours"],
            urgency=urgency,
            technician=technician["name"],
            briefing=briefing,
            predicted_passengers=pax,
        )

        # Send work order to Reporting Agent
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

        # Clear processed data
        self.fault_alerts.pop(equipment_id, None)
        self.diagnostic_reports.pop(equipment_id, None)

    def _classify_urgency(self, diagnostic, demand):
        action = diagnostic.get("action",    "monitor")
        ttf    = diagnostic.get("ttf_hours",  12.0)
        risk   = demand.get("risk_level",     "low") \
                 if demand else "low"
        pax    = demand.get("predicted_passengers", 0) \
                 if demand else 0

        if action == "emergency":           return "emergency"
        if ttf <= 3.0 and risk == "high":   return "emergency"
        if pax >= 300  and ttf <= 6.0:      return "emergency"
        if action == "scheduled":           return "scheduled"
        if risk == "medium" or ttf <= 8.0:  return "scheduled"
        return "monitor"

    def _select_technician(self, equipment_id):
        eq_type     = "elevator" if "ELV" in equipment_id \
                      else "escalator"
        specialists = [
            t for t in self.TECHNICIANS
            if t["speciality"] == eq_type
        ]
        return random.choice(specialists) if specialists \
               else random.choice(self.TECHNICIANS)

    def _generate_briefing(self, equipment_id, diagnostic,
                           demand, urgency):
        pax = demand["predicted_passengers"] if demand else "N/A"
        return (
            f"UNIT {equipment_id} | {urgency.upper()} | "
            f"{diagnostic['root_cause']} | "
            f"TTF: {diagnostic['ttf_hours']}h | "
            f"Load: {pax} passengers | "
            f"Action: {diagnostic['action']}"
        )

    async def setup(self):
        print("\n" + "="*55)
        print("  [Dispatch] 🤖 Dispatch Coordinator Agent STARTED")
        print("="*55 + "\n")
        store.update_agent("dispatch", "standby")
        store.add_message(
            "🤖 Dispatch Coordinator started — awaiting alerts",
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