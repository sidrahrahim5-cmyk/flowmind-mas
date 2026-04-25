# agents/people_flow_agent.py
import json
import random
import datetime
import spade
from spade.behaviour import PeriodicBehaviour

from config.settings import AGENTS, FORECAST_INTERVAL
from utils.message_templates import make_demand_forecast_msg
from utils.sensor_simulator import get_all_equipment_ids
from utils.event_store import store


class PeopleFlowAgent(spade.agent.Agent):

    TIME_PROFILES = {
        "morning_rush":   {"range": (200, 400), "label": "08:00-09:30"},
        "midday":         {"range": (80,  150), "label": "11:00-13:00"},
        "afternoon_rush": {"range": (180, 350), "label": "17:00-18:30"},
        "evening":        {"range": (40,  100), "label": "18:30-21:00"},
        "off_peak":       {"range": (10,   50), "label": "21:00-07:00"},
    }

    class GenerateForecastBehaviour(PeriodicBehaviour):

        async def run(self):
            equipment_ids = get_all_equipment_ids()
            time_profile  = self._get_time_profile()
            time_window   = time_profile["label"]
            pax_range     = time_profile["range"]

            print(f"\n[PeopleFlow] 📊 Generating forecasts "
                  f"— {time_window}")

            store.update_agent("people_flow", "forecasting")

            for eq_id in equipment_ids:
                predicted_pax = random.randint(*pax_range)
                risk_level    = self._assess_risk(predicted_pax)

                print(f"  {eq_id} → {predicted_pax} pax "
                      f"| Risk: {risk_level.upper()}")

                # Update event store forecast
                store.update_forecast(
                    equipment_id=eq_id,
                    passengers=predicted_pax,
                    risk=risk_level,
                    time_window=time_window,
                )

                # Send forecast to Dispatch
                msg = make_demand_forecast_msg(
                    to=AGENTS["dispatch"],
                    equipment_id=eq_id,
                    predicted_passengers=predicted_pax,
                    time_window=time_window,
                    risk_level=risk_level,
                )
                await self.send(msg)

            store.add_message(
                f"📊 Demand forecasts sent for all units "
                f"— window: {time_window}",
                "flow", "people_flow"
            )
            print("[PeopleFlow] 📤 Forecasts sent → Dispatch")

        def _get_time_profile(self):
            hour     = datetime.datetime.now().hour
            profiles = PeopleFlowAgent.TIME_PROFILES
            if 8  <= hour < 10: return profiles["morning_rush"]
            elif 11 <= hour < 14: return profiles["midday"]
            elif 17 <= hour < 19: return profiles["afternoon_rush"]
            elif 19 <= hour < 21: return profiles["evening"]
            else: return profiles["off_peak"]

        def _assess_risk(self, predicted_passengers):
            if predicted_passengers   >= 300: return "high"
            elif predicted_passengers >= 150: return "medium"
            else: return "low"

    async def setup(self):
        print("\n" + "="*55)
        print("  [PeopleFlow] 🤖 People Flow Agent STARTED")
        print("="*55 + "\n")
        store.update_agent("people_flow", "starting")
        store.add_message(
            "🤖 People Flow Agent started — forecasting demand",
            "system", "people_flow"
        )
        self.add_behaviour(
            self.GenerateForecastBehaviour(period=FORECAST_INTERVAL)
        )