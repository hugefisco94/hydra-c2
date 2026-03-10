from fastapi import FastAPI
from fastapi.testclient import TestClient

from hydra_c2.wargame.config import wargame_config
from hydra_c2.wargame.router import wargame_router


def create_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(wargame_router)
    return TestClient(app)


def test_wargame_health() -> None:
    client = create_test_client()
    response = client.get("/wargame/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mode"] == wargame_config.mode
    assert body["briefing_only"] is True


def test_wargame_policy() -> None:
    client = create_test_client()
    response = client.get("/wargame/policy")

    assert response.status_code == 200
    body = response.json()
    assert body["app_name"] == wargame_config.app_name
    assert body["allowed_interaction"] == "authentication plus synthetic briefing"
    assert body["guardrails"] == wargame_config.guardrails


def test_wargame_login_success() -> None:
    client = create_test_client()
    response = client.post(
        "/wargame/auth/login",
        json={"username": "analyst", "password": "defense-only"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "authenticated"
    assert body["session_token"] == wargame_config.briefing_session_token


def test_wargame_login_failure() -> None:
    client = create_test_client()
    response = client.post(
        "/wargame/auth/login",
        json={"username": "analyst", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials for the defense-only demo."


def test_wargame_briefing_requires_session() -> None:
    client = create_test_client()
    response = client.get("/wargame/scenario/briefing")

    assert response.status_code == 403
    assert response.json()["detail"] == "Briefing access requires a valid synthetic demo session."


def test_wargame_briefing_with_valid_session() -> None:
    client = create_test_client()
    response = client.get(
        "/wargame/scenario/briefing",
        headers={"X-Demo-Session": wargame_config.briefing_session_token},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "briefing_ready"
    assert body["scenario"]["scenario_id"] == wargame_config.demo_scenario.scenario_id
    assert body["boundary"] == "synthetic-briefing-only"


def test_wargame_config_defaults() -> None:
    assert wargame_config.app_name == "HYDRA Defense Wargame"
    assert wargame_config.mode == "defensive-simulation"
    assert wargame_config.briefing_only is True
    assert wargame_config.c2_integration is True
    assert wargame_config.demo_user.username == "analyst"
