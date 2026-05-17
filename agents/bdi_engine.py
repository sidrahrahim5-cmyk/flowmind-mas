# agents/bdi_engine.py
# FlowMind – BDI Engine
# Provides Belief, Goal, and Plan reasoning for DispatchCoordinatorAgent

from datetime import datetime


# ─────────────────────────────────────────────────────────────
# BELIEF BASE
# Stores what the agent currently knows about the world.
# Beliefs are updated as new messages arrive from other agents.
# ─────────────────────────────────────────────────────────────

class BeliefBase:

    def __init__(self):
        # Key: equipment_id → dict of known facts
        self._beliefs = {}

    def update(self, equipment_id: str, key: str, value):
        """Update one belief about a specific equipment unit."""
        if equipment_id not in self._beliefs:
            self._beliefs[equipment_id] = {}
        self._beliefs[equipment_id][key] = value
        print(f"[BDI:Belief] Updated — {equipment_id}.{key} = {value}")

    def get(self, equipment_id: str, key: str, default=None):
        """Retrieve a belief about a specific equipment unit."""
        return self._beliefs.get(equipment_id, {}).get(key, default)

    def get_all(self, equipment_id: str) -> dict:
        """Return all beliefs about one equipment unit."""
        return self._beliefs.get(equipment_id, {})

    def has(self, equipment_id: str, key: str) -> bool:
        """Check if a belief exists."""
        return key in self._beliefs.get(equipment_id, {})

    def clear(self, equipment_id: str):
        """Clear all beliefs about an equipment unit after dispatch."""
        if equipment_id in self._beliefs:
            del self._beliefs[equipment_id]
            print(f"[BDI:Belief] Cleared all beliefs for {equipment_id}")

    def summary(self, equipment_id: str) -> str:
        """Human-readable belief summary for logging."""
        b = self.get_all(equipment_id)
        if not b:
            return f"No beliefs for {equipment_id}"
        lines = [f"  Beliefs for {equipment_id}:"]
        for k, v in b.items():
            lines.append(f"    {k}: {v}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# GOAL MANAGER
# Defines what the agent wants to achieve.
# Goals are prioritized — higher number = higher priority.
# ─────────────────────────────────────────────────────────────

class Goal:
    # Goal priority constants (higher = more important)
    PASSENGER_SAFETY   = 100   # Never compromise passenger safety
    RESTORE_SERVICE    = 80    # Get equipment back online fast
    DISPATCH_TECHNICIAN = 70   # Send a technician
    MINIMIZE_DISRUPTION = 60   # Avoid unnecessary shutdowns
    MONITOR_ONLY       = 40    # Low risk — just watch


class GoalManager:

    def __init__(self):
        # Active goals: equipment_id → list of (priority, goal_name, reason)
        self._goals = {}

    def add_goal(self, equipment_id: str, priority: int,
                 goal_name: str, reason: str):
        """Add a goal for an equipment unit."""
        if equipment_id not in self._goals:
            self._goals[equipment_id] = []
        self._goals[equipment_id].append((priority, goal_name, reason))
        # Keep sorted — highest priority first
        self._goals[equipment_id].sort(key=lambda x: x[0], reverse=True)
        print(f"[BDI:Goal] Added — {equipment_id} | "
              f"[P{priority}] {goal_name} | Reason: {reason}")

    def get_top_goal(self, equipment_id: str):
        """Return the highest priority goal for this equipment."""
        goals = self._goals.get(equipment_id, [])
        if not goals:
            return None
        return goals[0]  # (priority, goal_name, reason)

    def get_all_goals(self, equipment_id: str):
        """Return all active goals sorted by priority."""
        return self._goals.get(equipment_id, [])

    def has_conflict(self, equipment_id: str) -> bool:
        """
        Detect conflicting goals.
        Conflict = RESTORE_SERVICE and MINIMIZE_DISRUPTION both active
        while passengers are at risk.
        This is the Scenario 2 trigger.
        """
        goals = self._goals.get(equipment_id, [])
        goal_names = [g[1] for g in goals]
        return (
            "RESTORE_SERVICE" in goal_names and
            "MINIMIZE_DISRUPTION" in goal_names
        )

    def clear(self, equipment_id: str):
        """Clear all goals after dispatch decision is made."""
        if equipment_id in self._goals:
            del self._goals[equipment_id]
            print(f"[BDI:Goal] Cleared all goals for {equipment_id}")

    def summary(self, equipment_id: str) -> str:
        """Human-readable goal summary for logging."""
        goals = self.get_all_goals(equipment_id)
        if not goals:
            return f"No goals for {equipment_id}"
        lines = [f"  Goals for {equipment_id}:"]
        for priority, name, reason in goals:
            lines.append(f"    [P{priority}] {name} — {reason}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# PLAN LIBRARY
# Selects and executes the right plan based on beliefs + goals.
# Each plan returns a dispatch decision dict.
# ─────────────────────────────────────────────────────────────

class PlanLibrary:

    @staticmethod
    def select_plan(equipment_id: str,
                    beliefs: BeliefBase,
                    goals: GoalManager) -> dict:
        """
        Core BDI reasoning:
        Look at beliefs → evaluate goals → pick and run the right plan.
        Returns a decision dict with urgency, action, reasoning, scenario.
        """

        top_goal = goals.get_top_goal(equipment_id)
        conflict  = goals.has_conflict(equipment_id)

        # ── Pull relevant beliefs ──────────────────────────────
        severity        = beliefs.get(equipment_id, "severity",        "low")
        ttf_hours       = beliefs.get(equipment_id, "ttf_hours",        12.0)
        action          = beliefs.get(equipment_id, "action",          "monitor")
        passengers      = beliefs.get(equipment_id, "passengers",       0)
        risk_level      = beliefs.get(equipment_id, "risk_level",      "low")
        root_cause      = beliefs.get(equipment_id, "root_cause",      "Unknown")
        is_rush_hour    = beliefs.get(equipment_id, "is_rush_hour",    False)

        print(f"\n[BDI:Plan] Selecting plan for {equipment_id}")
        print(f"  Top goal : {top_goal}")
        print(f"  Conflict : {conflict}")
        print(f"  Rush hour: {is_rush_hour} | Passengers: {passengers}")
        print(f"  TTF      : {ttf_hours}h | Severity: {severity}")

        # ── SCENARIO 2: Conflicting Goals ──────────────────────
        # Fault detected AND passengers are at high risk simultaneously.
        # Agent must reason about trade-off between safety and service.
        if conflict and is_rush_hour and passengers >= 200:
            return PlanLibrary._plan_conflict_resolution(
                equipment_id, beliefs, ttf_hours, passengers,
                severity, root_cause, risk_level
            )

        # ── SCENARIO 1: Routine Fault Dispatch ────────────────
        # No conflict — straightforward goal execution.
        return PlanLibrary._plan_routine_dispatch(
            equipment_id, beliefs, ttf_hours, passengers,
            severity, action, root_cause, top_goal
        )

    # ── PLAN A: Routine Dispatch (Scenario 1) ─────────────────
    @staticmethod
    def _plan_routine_dispatch(equipment_id, beliefs, ttf_hours,
                               passengers, severity, action,
                               root_cause, top_goal) -> dict:
        """
        Scenario 1 — Normal fault with no passenger conflict.
        Goal: dispatch technician, restore service.
        Decision is straightforward based on TTF and severity.
        """
        if action == "emergency" or ttf_hours <= 3.0:
            urgency = "emergency"
            reasoning = (
                f"Fault requires immediate attention. "
                f"TTF={ttf_hours}h is critically low. "
                f"Root cause: {root_cause}. "
                f"Plan: Emergency dispatch to prevent failure."
            )
        elif action == "scheduled" or ttf_hours <= 8.0:
            urgency = "scheduled"
            reasoning = (
                f"Fault detected but not immediately critical. "
                f"TTF={ttf_hours}h allows scheduled repair. "
                f"Root cause: {root_cause}. "
                f"Plan: Schedule technician within safe window."
            )
        else:
            urgency = "monitor"
            reasoning = (
                f"Low severity fault. TTF={ttf_hours}h — no immediate risk. "
                f"Root cause: {root_cause}. "
                f"Plan: Monitor and reassess on next cycle."
            )

        return {
            "scenario":   "SCENARIO_1_ROUTINE_FAULT",
            "urgency":    urgency,
            "reasoning":  reasoning,
            "conflict":   False,
            "goal_used":  top_goal[1] if top_goal else "DISPATCH_TECHNICIAN",
        }

    # ── PLAN B: Conflict Resolution (Scenario 2) ─────────────
    @staticmethod
    def _plan_conflict_resolution(equipment_id, beliefs, ttf_hours,
                                  passengers, severity, root_cause,
                                  risk_level) -> dict:
        """
        Scenario 2 — Conflicting goals: fix fault vs keep service running.
        Agent must reason under uncertainty and balance two competing goals:
          - RESTORE_SERVICE: equipment is failing, needs repair
          - MINIMIZE_DISRUPTION: hundreds of passengers depend on it NOW

        BDI decision logic:
          If TTF < 2h  → passenger safety wins → emergency shutdown + dispatch
          If TTF 2–5h  → partial service + urgent dispatch (compromise plan)
          If TTF > 5h  → keep running + schedule repair (service wins short-term)
        """

        if ttf_hours < 2.0:
            # Safety must win — equipment will fail very soon
            urgency = "emergency"
            reasoning = (
                f"CONFLICT DETECTED — Rush hour with {passengers} passengers "
                f"vs failing equipment (TTF={ttf_hours}h). "
                f"DECISION: Passenger safety overrides service continuity. "
                f"TTF is critically low — equipment must be shut down immediately. "
                f"MINIMIZE_DISRUPTION goal SUSPENDED. "
                f"RESTORE_SERVICE + PASSENGER_SAFETY goals ACTIVATED. "
                f"Plan: Emergency dispatch, take unit offline."
            )
            shutdown = True

        elif ttf_hours <= 5.0:
            # Compromise — urgent but not immediate shutdown
            urgency = "urgent"
            reasoning = (
                f"CONFLICT DETECTED — Rush hour with {passengers} passengers "
                f"vs degrading equipment (TTF={ttf_hours}h). "
                f"DECISION: Compromise plan — keep unit running at reduced load "
                f"while dispatching technician urgently. "
                f"Both RESTORE_SERVICE and MINIMIZE_DISRUPTION partially satisfied. "
                f"Plan: Urgent dispatch, reduce load, alert passengers."
            )
            shutdown = False

        else:
            # Service continuity wins — enough time before failure
            urgency = "scheduled"
            reasoning = (
                f"CONFLICT DETECTED — Rush hour with {passengers} passengers "
                f"vs fault detected (TTF={ttf_hours}h). "
                f"DECISION: Service continuity prioritized. "
                f"TTF={ttf_hours}h gives enough buffer to keep unit running through peak. "
                f"MINIMIZE_DISRUPTION goal wins this cycle. "
                f"Plan: Schedule repair after rush hour ends."
            )
            shutdown = False

        return {
            "scenario":   "SCENARIO_2_CONFLICT_RESOLUTION",
            "urgency":    urgency,
            "reasoning":  reasoning,
            "conflict":   True,
            "shutdown":   shutdown,
            "goal_used":  "CONFLICT_RESOLUTION",
            "passengers_at_risk": passengers,
        }