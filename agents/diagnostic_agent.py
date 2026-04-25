# agents/diagnostic_agent.py
import json
import random
import spade
from spade.behaviour import CyclicBehaviour
from spade.template import Template

from config.settings import AGENTS
from utils.message_templates import make_diagnostic_report_msg
from utils.event_store import store


class DiagnosticAgent(spade.agent.Agent):

    FAILURE_PATTERNS = {
        "high_vibration": {
            "root_cause": "Bearing wear — abnormal vibration signature",
            "base_ttf": 4.0, "action": "emergency",
        },
        "high_temperature": {
            "root_cause": "Motor overheating — thermal stress on drive unit",
            "base_ttf": 6.0, "action": "scheduled",
        },
        "high_door_cycles": {
            "root_cause": "Door mechanism wear — excessive cycle count",
            "base_ttf": 8.0, "action": "scheduled",
        },
        "multiple_faults": {
            "root_cause": "Multiple system anomalies — combined failure risk",
            "base_ttf": 2.0, "action": "emergency",
        },
        "unknown": {
            "root_cause": "Unclassified anomaly — manual inspection required",
            "base_ttf": 12.0, "action": "monitor",
        },
    }

    class ReceiveFaultSignatureBehaviour(CyclicBehaviour):

        async def run(self):
            msg = await self.receive(timeout=10)
            if msg is None:
                return

            try:
                data = json.loads(msg.body)
                if data.get("msg_type") != "fault_signature":
                    return

                equipment_id = data["equipment_id"]
                severity     = data["severity"]
                vibration    = data["vibration"]
                temperature  = data["temperature"]
                door_cycles  = data["door_cycles"]

                print(f"\n[Diagnostic] 📥 Fault signature "
                      f"received for {equipment_id}")

                store.update_agent("diagnostic", "analysing...")
                store.add_message(
                    f"📥 Fault signature received "
                    f"for {equipment_id} — analysing...",
                    "diag", "diagnostic"
                )

                # Identify root cause
                pattern    = self._identify_pattern(
                    vibration, temperature, door_cycles
                )
                root_cause = pattern["root_cause"]
                action     = pattern["action"]
                ttf_hours  = self._estimate_ttf(
                    pattern["base_ttf"], severity
                )

                print(f"[Diagnostic] 🔍 Root Cause: {root_cause}")
                print(f"[Diagnostic] ⏱  TTF: {ttf_hours}h")
                print(f"[Diagnostic] 🎯 Action: {action.upper()}")

                store.update_agent("diagnostic", "report ready")
                store.add_message(
                    f"🔍 Root cause: {root_cause} | "
                    f"TTF: {ttf_hours}h | "
                    f"Action: {action.upper()}",
                    "diag", "diagnostic"
                )

                # Send diagnostic report to Dispatch
                report_msg = make_diagnostic_report_msg(
                    to=AGENTS["dispatch"],
                    equipment_id=equipment_id,
                    root_cause=root_cause,
                    ttf_hours=ttf_hours,
                    action=action,
                    severity=severity,
                )
                await self.send(report_msg)

                store.add_message(
                    f"📤 Diagnostic report → "
                    f"Dispatch Coordinator ({equipment_id})",
                    "diag", "diagnostic"
                )
                print(
                    f"[Diagnostic] 📤 Report sent "
                    f"→ Dispatch ({equipment_id})"
                )

            except Exception as e:
                print(f"[Diagnostic] ❌ Error: {e}")

        def _identify_pattern(
            self, vibration, temperature, door_cycles
        ):
            patterns   = DiagnosticAgent.FAILURE_PATTERNS
            high_vib   = vibration    > 7.0
            high_temp  = temperature  > 75.0
            high_doors = door_cycles  > 950
            fault_count = sum([high_vib, high_temp, high_doors])

            if fault_count >= 2:
                return patterns["multiple_faults"]
            elif high_vib:
                return patterns["high_vibration"]
            elif high_temp:
                return patterns["high_temperature"]
            elif high_doors:
                return patterns["high_door_cycles"]
            else:
                return patterns["unknown"]

        def _estimate_ttf(self, base_ttf, severity):
            multipliers = {"low": 1.5, "medium": 1.0, "high": 0.5}
            multiplier  = multipliers.get(severity, 1.0)
            variation   = random.uniform(0.8, 1.2)
            return round(base_ttf * multiplier * variation, 1)

    async def setup(self):
        print("\n" + "="*55)
        print("  [Diagnostic] 🤖 Diagnostic Agent STARTED")
        print("="*55 + "\n")
        store.update_agent("diagnostic", "waiting")
        store.add_message(
            "🤖 Diagnostic Agent started — waiting for fault signatures",
            "system", "diagnostic"
        )
        template = Template()
        template.set_metadata("ontology", "fault-detection")
        self.add_behaviour(
            self.ReceiveFaultSignatureBehaviour(), template
        )