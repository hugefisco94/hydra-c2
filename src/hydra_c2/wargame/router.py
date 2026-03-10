from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import wargame_config

WEB_DIR = Path(__file__).resolve().parent / "web"

wargame_router = APIRouter(prefix="/wargame", tags=["Wargame Simulation"])


class LoginRequest(BaseModel):
    username: str
    password: str


@wargame_router.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "mode": wargame_config.mode,
        "login_only": wargame_config.login_only,
        "briefing_only": wargame_config.briefing_only,
        "public_use_notice": wargame_config.public_use_notice,
        "c2_integration": wargame_config.c2_integration,
    }


@wargame_router.get("/policy")
def policy() -> dict[str, object]:
    return {
        "app_name": wargame_config.app_name,
        "mode": wargame_config.mode,
        "login_only": wargame_config.login_only,
        "briefing_only": wargame_config.briefing_only,
        "notice": wargame_config.public_use_notice,
        "guardrails": wargame_config.guardrails,
        "allowed_interaction": "authentication plus synthetic briefing",
        "c2_integration": wargame_config.c2_integration,
    }


@wargame_router.post("/auth/login")
def login(credentials: LoginRequest) -> dict[str, object]:
    expected = wargame_config.demo_user
    if credentials.username != expected.username or credentials.password != expected.password:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials for the defense-only demo.",
        )

    return {
        "status": "authenticated",
        "next_step": "synthetic_briefing",
        "message": (
            "Login succeeded. Only a synthetic briefing is available after "
            "authentication to preserve a defensive-only scope."
        ),
        "session_token": wargame_config.briefing_session_token,
        "guardrails": wargame_config.guardrails,
    }


@wargame_router.get("/scenario/briefing")
def scenario_briefing(x_demo_session: Annotated[str, Header()] = "") -> dict[str, object]:
    if x_demo_session != wargame_config.briefing_session_token:
        raise HTTPException(
            status_code=403,
            detail="Briefing access requires a valid synthetic demo session.",
        )

    scenario = wargame_config.demo_scenario
    return {
        "status": "briefing_ready",
        "scenario": scenario.model_dump(),
        "guardrails": wargame_config.guardrails,
        "boundary": "synthetic-briefing-only",
    }


@wargame_router.get("/scenario/briefing/enhanced")
def scenario_briefing_enhanced(
    request: Request,
    x_demo_session: Annotated[str, Header()] = "",
) -> dict[str, object]:
    if x_demo_session != wargame_config.briefing_session_token:
        raise HTTPException(
            status_code=403,
            detail="Briefing access requires a valid synthetic demo session.",
        )

    scenario = wargame_config.demo_scenario.model_dump()
    c2_snapshot: dict[str, object] = {
        "integration_available": False,
        "actors_total": 0,
        "sample_callsigns": [],
    }
    if wargame_config.c2_integration:
        actors = getattr(request.app.state, "standalone_actors", None)
        if isinstance(actors, list):
            sample_callsigns = [
                str(actor.get("name", "")) for actor in actors[:5] if isinstance(actor, dict) and actor.get("name")
            ]
            c2_snapshot = {
                "integration_available": True,
                "actors_total": len(actors),
                "sample_callsigns": sample_callsigns,
            }

    return {
        "status": "briefing_ready",
        "scenario": scenario,
        "guardrails": wargame_config.guardrails,
        "boundary": "synthetic-briefing-only",
        "c2_snapshot": c2_snapshot,
    }


def mount_wargame_ui(app: FastAPI) -> None:
    def wargame_index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html", media_type="text/html")

    def wargame_app_js() -> FileResponse:
        return FileResponse(WEB_DIR / "app.js", media_type="application/javascript")

    def wargame_styles() -> FileResponse:
        return FileResponse(WEB_DIR / "styles.css", media_type="text/css")

    app.add_api_route("/wargame/", wargame_index, methods=["GET"])
    app.add_api_route("/wargame/app.js", wargame_app_js, methods=["GET"])
    app.add_api_route("/wargame/styles.css", wargame_styles, methods=["GET"])
