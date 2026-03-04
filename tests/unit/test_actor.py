"""Unit tests for Actor domain entity."""

import pytest
from hydra_c2.domain.entities.actor import Actor, ActorType, Affiliation, GeoPosition


class TestGeoPosition:
    """Tests for GeoPosition value object."""

    def test_valid_position(self) -> None:
        pos = GeoPosition(latitude=37.5665, longitude=126.9780)
        assert pos.latitude == 37.5665
        assert pos.longitude == 126.9780

    def test_with_altitude(self) -> None:
        pos = GeoPosition(latitude=37.5665, longitude=126.9780, altitude_m=50.0)
        assert pos.altitude_m == 50.0

    def test_invalid_latitude(self) -> None:
        with pytest.raises(ValueError, match="Invalid latitude"):
            GeoPosition(latitude=91.0, longitude=0.0)

    def test_invalid_longitude(self) -> None:
        with pytest.raises(ValueError, match="Invalid longitude"):
            GeoPosition(latitude=0.0, longitude=181.0)

    def test_to_wkt_2d(self) -> None:
        pos = GeoPosition(latitude=37.5665, longitude=126.9780)
        assert pos.to_wkt() == "POINT(126.978 37.5665)"

    def test_to_wkt_3d(self) -> None:
        pos = GeoPosition(latitude=37.5665, longitude=126.9780, altitude_m=50.0)
        assert pos.to_wkt() == "POINTZ(126.978 37.5665 50.0)"


class TestActor:
    """Tests for Actor domain entity."""

    def test_create_default_actor(self) -> None:
        actor = Actor()
        assert actor.callsign == ""
        assert actor.affiliation == Affiliation.UNKNOWN
        assert actor.actor_type == ActorType.UNKNOWN
        assert actor.position is None

    def test_create_named_actor(self) -> None:
        actor = Actor(
            callsign="ALPHA-1",
            actor_type=ActorType.PERSON,
            affiliation=Affiliation.FRIENDLY,
        )
        assert actor.callsign == "ALPHA-1"
        assert actor.affiliation == Affiliation.FRIENDLY

    def test_update_position(self) -> None:
        actor = Actor(callsign="BRAVO-2")
        pos = GeoPosition(latitude=37.5665, longitude=126.9780)
        actor.update_position(pos)
        assert actor.position == pos
        assert actor.position is not None

    def test_is_stale_fresh(self) -> None:
        actor = Actor(callsign="CHARLIE-3")
        assert not actor.is_stale(max_age_seconds=3600)

    def test_mil_std_2525b_sidc(self) -> None:
        actor = Actor(affiliation=Affiliation.FRIENDLY)
        assert actor.mil_std_2525b_sidc == "SFGP------"

        actor_hostile = Actor(affiliation=Affiliation.HOSTILE)
        assert actor_hostile.mil_std_2525b_sidc == "SHGP------"
