# agents/reporting_agent.py
import json
import datetime
import spade
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from spade.template import Template

from config.settings import REPORT_INTERVAL
from utils.event_store import store


class ReportingAgent(spade.agent.Agent):

    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.incidents   = []
        self.shift_start = datetime.datetime.now()
        self.report_count = 0

    class ReceiveDispatchDecisionBehaviour(CyclicBehaviour):

        async def run(self):
            msg = await self.receive(timeout=10)
            if msg is None:
                return
            try:
                data = json.loads(msg.body)
                if data.get("msg_type") != "dispatch_decision":
                    return

                data["received_at"] = datetime.datetime.now()\
                                      .strftime("%Y-%m-%d %H:%M:%S")
                self.agent.incidents.append(data)

                print(f"\n[Reporting] 📥 Work order received "
                      f"— {data['equipment_id']}")
                print(f"  Technician: {data['technician']}")
                print(f"  Urgency   : {data['urgency'].upper()}")
                print(f"  Total this shift: "
                      f"{len(self.agent.incidents)}")

                store.update_agent("reporting", "logging incident")
                store.add_message(
                    f"📥 Work order received — "
                    f"{data['equipment_id']} | "
                    f"{data['urgency'].upper()} | "
                    f"→ {data['technician']}",
                    "report", "reporting"
                )

            except Exception as e:
                print(f"[Reporting] ❌ Error: {e}")

    class GenerateShiftReportBehaviour(PeriodicBehaviour):

        async def run(self):
            agent = self.agent
            if not agent.incidents:
                print(f"\n[Reporting] 📋 No incidents yet...")
                store.add_message(
                    "📋 Shift report check — no incidents yet",
                    "report", "reporting"
                )
                return

            agent.report_count += 1
            report = agent._generate_report()

            print(f"\n[Reporting] 📋 SHIFT REPORT "
                  f"#{agent.report_count}")
            print("=" * 55)
            print(report)
            print("=" * 55)

            store.update_agent(
                "reporting",
                f"report #{agent.report_count} delivered"
            )
            store.add_message(
                f"📋 Shift report #{agent.report_count} generated "
                f"— {len(agent.incidents)} incidents | "
                f"{store.kpis['downtime_saved']} min saved",
                "report", "reporting"
            )
            agent.incidents = []

    def _generate_report(self):
        now           = datetime.datetime.now()
        shift_minutes = int(
            (now - self.shift_start).total_seconds() / 60
        )
        total      = len(self.incidents)
        emergency  = sum(
            1 for i in self.incidents if i["urgency"] == "emergency"
        )
        scheduled  = sum(
            1 for i in self.incidents if i["urgency"] == "scheduled"
        )
        monitor    = sum(
            1 for i in self.incidents if i["urgency"] == "monitor"
        )
        downtime   = emergency * 47 + scheduled * 20
        equip_list = list(set(
            i["equipment_id"] for i in self.incidents
        ))
        techs      = list(set(
            i["technician"] for i in self.incidents
        ))

        lines = ""
        for idx, inc in enumerate(self.incidents, 1):
            lines += (
                f"\n  {idx}. [{inc['urgency'].upper()}] "
                f"{inc['equipment_id']} — "
                f"{inc['root_cause']} "
                f"(TTF: {inc['ttf_hours']}h) "
                f"→ {inc['technician']}"
            )

        return f"""
FLOWMIND REPORT #{self.report_count}
Generated : {now.strftime("%Y-%m-%d %H:%M:%S")}
Shift     : {self.shift_start.strftime("%H:%M")} — \
{now.strftime("%H:%M")} ({shift_minutes} min)

SUMMARY
Total     : {total} | Emergency: {emergency} | \
Scheduled: {scheduled} | Monitor: {monitor}
Downtime  : ~{downtime} minutes avoided
Equipment : {", ".join(equip_list)}
Technicians: {", ".join(techs)}

INCIDENTS{lines}

All incidents actioned. Monitoring continues.
        """.strip()

    async def setup(self):
        print("\n" + "="*55)
        print("  [Reporting] 🤖 Reporting Agent STARTED")
        print("="*55 + "\n")
        store.update_agent("reporting", "collecting")
        store.add_message(
            "🤖 Reporting Agent started — collecting incidents",
            "system", "reporting"
        )

        t1 = Template()
        t1.set_metadata("ontology", "dispatch-decision")
        b1 = self.ReceiveDispatchDecisionBehaviour()
        self.add_behaviour(b1, t1)

        b2 = self.GenerateShiftReportBehaviour(
            period=REPORT_INTERVAL
        )
        self.add_behaviour(b2)