from pydantic import BaseModel, Field


class DemoUser(BaseModel):
    username: str = "analyst"
    password: str = "defense-only"


class DemoScenario(BaseModel):
    scenario_id: str = "synthetic-harbor-01"
    title: str = "Synthetic Harbor Readiness Brief"
    classification: str = "UNCLASSIFIED // SYNTHETIC TRAINING"
    region: str = "Bluewater Training Grid"
    summary: str = (
        "A synthetic readiness exercise for security analysts focused on "
        "triage, communications discipline, and escalation hygiene."
    )
    objectives: list[str] = Field(
        default_factory=lambda: [
            "Validate analyst login and policy acknowledgement flow",
            "Review synthetic observations without connecting to live systems",
            "Practice tabletop escalation notes for a training cell",
        ]
    )
    watch_items: list[str] = Field(
        default_factory=lambda: [
            "Synthetic radar gap near Pier 4",
            "Synthetic identity mismatch on support vessel Bravo",
            "Synthetic help-desk report referencing abnormal badge retries",
        ]
    )
    permitted_actions: list[str] = Field(
        default_factory=lambda: [
            "Read the briefing",
            "Record tabletop observations",
            "Escalate to a human training facilitator",
        ]
    )
    blocked_actions: list[str] = Field(
        default_factory=lambda: [
            "No live control actions",
            "No device or network changes",
            "No external system connectivity",
        ]
    )
    checklist_items: list[str] = Field(
        default_factory=lambda: [
            "Confirm the exercise remains synthetic-only",
            "Record the three highest-priority watch items",
            "Identify which facilitator should receive the briefing note",
            "Verify no live systems or endpoints are referenced",
        ]
    )
    report_sections: list[str] = Field(
        default_factory=lambda: [
            "Situation Summary",
            "Observed Signals",
            "Recommended Human Escalation",
            "Boundary Compliance Notes",
        ]
    )


class WargameConfig(BaseModel):
    app_name: str = "HYDRA Defense Wargame"
    mode: str = "defensive-simulation"
    login_only: bool = False
    briefing_only: bool = True
    public_use_notice: str = (
        "This simulator is limited to defensive training and intentionally "
        "stops at a synthetic post-login briefing boundary."
    )
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "No implants, covert callbacks, or agent dispatch",
            "No remote control, footholds, or data removal",
            "No live control-plane features",
            "Only synthetic or policy metadata may be shown",
        ]
    )
    demo_user: DemoUser = Field(default_factory=DemoUser)
    briefing_session_token: str = "synthetic-briefing-access"
    demo_scenario: DemoScenario = Field(default_factory=DemoScenario)
    c2_integration: bool = True


wargame_config = WargameConfig()
