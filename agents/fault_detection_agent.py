# agents/fault_detection_agent.py
import json
import asyncio
import spade
from spade.behaviour import PeriodicBehaviour

from config.settings import AGENTS, SENSOR_CHECK_INTERVAL
from utils.sensor_simulator import (
    get_sensor_reading, classify_severity, get_all_equipment_ids
)
from utils.message_templates import (
    make_fault_signature_msg, make_fault_alert_msg
)
from utils.event_store import store


class FaultDetectionAgent(spade.agent.Agent):

    class MonitorSensorsBehaviour(PeriodicBehaviour):

        async def run(self):
            equipment_ids = get_all_equipment_ids()

            for eq_id in equipment_ids:
                reading  = get_sensor_reading(eq_id)
                severity = classify_severity(reading)

                # Update event store with sensor reading
                store.update_sensor(eq_id, reading, severity)

                if severity == "normal":
                    print(
                        f"[FaultDetection] ✅ {eq_id} — Normal | "
                        f"Vib={reading['vibration']} "
                        f"Temp={reading['temperature']}°C "
                        f"Doors={reading['door_cycles']}"
                    )
                    store.add_message(
                        f"✅ {eq_id} — Normal readings",
                        "normal", "fault_detection"
                    )
                    store.update_agent("fault_detection", "monitoring")
                    continue

                # Anomaly detected
                print(f"\n[FaultDetection] 🚨 ANOMALY on {eq_id}!")
                print(f"  Severity  : {severity.upper()}")
                print(f"  Vibration : {reading['vibration']}")
                print(f"  Temp      : {reading['temperature']}°C")
                print(f"  DoorCycles: {reading['door_cycles']}")

                store.update_agent(
                    "fault_detection", "anomaly detected!"
                )
                store.add_message(
                    f"🚨 ANOMALY on {eq_id} — "
                    f"Vib:{reading['vibration']} "
                    f"Temp:{reading['temperature']}°C "
                    f"Severity:{severity.upper()}",
                    "fault", "fault_detection"
                )

                await self._alert_diagnostic(reading, severity)
                await self._alert_dispatch(reading, severity)
                await asyncio.sleep(0.5)

        async def _alert_diagnostic(self, reading, severity):
            msg = make_fault_signature_msg(
                to=AGENTS["diagnostic"],
                reading=reading, severity=severity
            )
            await self.send(msg)
            store.add_message(
                f"📤 Fault signature → Diagnostic "
                f"({reading['equipment_id']})",
                "fault", "fault_detection"
            )
            print(
                f"[FaultDetection] 📤 Fault signature sent "
                f"→ Diagnostic ({reading['equipment_id']})"
            )

        async def _alert_dispatch(self, reading, severity):
            msg = make_fault_alert_msg(
                to=AGENTS["dispatch"],
                reading=reading, severity=severity
            )
            await self.send(msg)
            store.add_message(
                f"📤 Fault alert → Dispatch "
                f"({reading['equipment_id']})",
                "fault", "fault_detection"
            )
            print(
                f"[FaultDetection] 📤 Fault alert sent "
                f"→ Dispatch ({reading['equipment_id']})"
            )

    async def setup(self):
        print("\n" + "="*55)
        print("  [FaultDetection] 🤖 Fault Detection Agent STARTED")
        print("="*55 + "\n")
        store.update_agent("fault_detection", "monitoring")
        store.add_message(
            "🤖 Fault Detection Agent started — monitoring all units",
            "system", "fault_detection"
        )
        self.add_behaviour(
            self.MonitorSensorsBehaviour(period=SENSOR_CHECK_INTERVAL)
        )