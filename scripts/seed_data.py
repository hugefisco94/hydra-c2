#!/usr/bin/env python3
"""HYDRA-C2 Seed Data — Insert 15 realistic military actors into PostGIS.

Usage:
    # Via API endpoint (recommended for remote):
    python scripts/seed_data.py --api http://134.199.207.172:8080

    # Direct database insert (requires DB access):
    python scripts/seed_data.py --direct
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

# ─── Actor definitions: 15 realistic military actors around Korean Peninsula ───

ACTORS = [
    # ── FRIENDLY (Blue Force) ──────────────────────────────────────────────
    {
        "id": str(uuid4()),
        "callsign": "ALPHA-1",
        "actor_type": "UNIT",
        "affiliation": "FRIENDLY",
        "lat": 37.5665,
        "lon": 126.9780,
        "alt": 50.0,
        "speed_mps": 0.0,
        "course_deg": 0.0,
        "source": "ATAK",
        "confidence": 0.95,
        "metadata": {"unit_type": "Infantry Battalion", "echelon": "BN", "branch": "ROK Army"},
    },
    {
        "id": str(uuid4()),
        "callsign": "VIPER-6",
        "actor_type": "VEHICLE",
        "affiliation": "FRIENDLY",
        "lat": 37.4563,
        "lon": 126.7052,
        "alt": 15.0,
        "speed_mps": 12.5,
        "course_deg": 45.0,
        "source": "ATAK",
        "confidence": 0.92,
        "metadata": {"vehicle_type": "K2 Black Panther MBT", "unit": "11th Mechanized Division"},
    },
    {
        "id": str(uuid4()),
        "callsign": "EAGLE-21",
        "actor_type": "AIRCRAFT",
        "affiliation": "FRIENDLY",
        "lat": 36.9600,
        "lon": 127.0300,
        "alt": 8500.0,
        "speed_mps": 250.0,
        "course_deg": 315.0,
        "source": "ATAK",
        "confidence": 0.98,
        "metadata": {"aircraft_type": "KF-21 Boramae", "squadron": "17th Fighter Wing"},
    },
    {
        "id": str(uuid4()),
        "callsign": "TRIDENT-3",
        "actor_type": "VESSEL",
        "affiliation": "FRIENDLY",
        "lat": 35.0794,
        "lon": 129.0800,
        "alt": 0.0,
        "speed_mps": 8.0,
        "course_deg": 180.0,
        "source": "AIS",
        "confidence": 0.97,
        "metadata": {"vessel_type": "Sejong the Great-class DDG", "hull": "DDG-991"},
    },
    {
        "id": str(uuid4()),
        "callsign": "RAVEN-7",
        "actor_type": "UAV",
        "affiliation": "FRIENDLY",
        "lat": 37.9000,
        "lon": 126.8500,
        "alt": 3000.0,
        "speed_mps": 45.0,
        "course_deg": 0.0,
        "source": "ATAK",
        "confidence": 0.90,
        "metadata": {"uav_type": "RQ-4 Global Hawk", "mission": "ISR"},
    },
    # ── HOSTILE (Red Force) ────────────────────────────────────────────────
    {
        "id": str(uuid4()),
        "callsign": "BEAR-1",
        "actor_type": "UNIT",
        "affiliation": "HOSTILE",
        "lat": 38.3200,
        "lon": 126.5500,
        "alt": 120.0,
        "speed_mps": 0.0,
        "course_deg": 0.0,
        "source": "SDR",
        "confidence": 0.65,
        "metadata": {"assessed_type": "Mechanized Infantry", "threat_level": "HIGH"},
    },
    {
        "id": str(uuid4()),
        "callsign": "FENCER-2",
        "actor_type": "AIRCRAFT",
        "affiliation": "HOSTILE",
        "lat": 39.0200,
        "lon": 125.7500,
        "alt": 10000.0,
        "speed_mps": 300.0,
        "course_deg": 135.0,
        "source": "SDR",
        "confidence": 0.72,
        "metadata": {"assessed_type": "Su-25 Frogfoot", "emitter": "RADAR-WARN"},
    },
    {
        "id": str(uuid4()),
        "callsign": "VENOM-5",
        "actor_type": "VEHICLE",
        "affiliation": "HOSTILE",
        "lat": 38.5100,
        "lon": 127.0100,
        "alt": 85.0,
        "speed_mps": 5.0,
        "course_deg": 210.0,
        "source": "SDR",
        "confidence": 0.58,
        "metadata": {"assessed_type": "TEL (Transporter Erector Launcher)", "priority": "CRITICAL"},
    },
    {
        "id": str(uuid4()),
        "callsign": "SHARK-9",
        "actor_type": "VESSEL",
        "affiliation": "HOSTILE",
        "lat": 37.5000,
        "lon": 124.5000,
        "alt": 0.0,
        "speed_mps": 15.0,
        "course_deg": 90.0,
        "source": "AIS",
        "confidence": 0.60,
        "metadata": {"assessed_type": "Nampo-class Frigate", "threat_level": "MEDIUM"},
    },
    {
        "id": str(uuid4()),
        "callsign": "GHOST-4",
        "actor_type": "TRANSMISSION_SOURCE",
        "affiliation": "HOSTILE",
        "lat": 38.7500,
        "lon": 125.9000,
        "alt": 0.0,
        "speed_mps": 0.0,
        "course_deg": 0.0,
        "source": "KRAKEN",
        "confidence": 0.45,
        "metadata": {"freq_mhz": 243.0, "signal_type": "ENCRYPTED_BURST", "rdf_bearing": 345.0},
    },
    # ── NEUTRAL ────────────────────────────────────────────────────────────
    {
        "id": str(uuid4()),
        "callsign": "JADE-EXPRESS",
        "actor_type": "VESSEL",
        "affiliation": "NEUTRAL",
        "lat": 34.5000,
        "lon": 128.5000,
        "alt": 0.0,
        "speed_mps": 10.0,
        "course_deg": 270.0,
        "source": "AIS",
        "confidence": 0.85,
        "metadata": {"vessel_type": "Container Ship", "mmsi": "440123456", "flag": "KR"},
    },
    {
        "id": str(uuid4()),
        "callsign": "KE-801",
        "actor_type": "AIRCRAFT",
        "affiliation": "NEUTRAL",
        "lat": 36.5700,
        "lon": 126.8000,
        "alt": 11000.0,
        "speed_mps": 240.0,
        "course_deg": 90.0,
        "source": "ADS-B",
        "confidence": 0.99,
        "metadata": {"airline": "Korean Air", "aircraft_type": "B777-300ER", "flight": "KE801"},
    },
    # ── UNKNOWN ────────────────────────────────────────────────────────────
    {
        "id": str(uuid4()),
        "callsign": "CONTACT-ALPHA",
        "actor_type": "UNKNOWN",
        "affiliation": "UNKNOWN",
        "lat": 37.7500,
        "lon": 125.2000,
        "alt": 500.0,
        "speed_mps": 35.0,
        "course_deg": 120.0,
        "source": "SDR",
        "confidence": 0.30,
        "metadata": {"first_detected": "2026-03-05T01:00:00Z", "rcs_dbsm": -5.0},
    },
    {
        "id": str(uuid4()),
        "callsign": "SHADOW-X",
        "actor_type": "UAV",
        "affiliation": "UNKNOWN",
        "lat": 38.0000,
        "lon": 126.2000,
        "alt": 1500.0,
        "speed_mps": 20.0,
        "course_deg": 180.0,
        "source": "KRAKEN",
        "confidence": 0.35,
        "metadata": {"assessed_type": "Small UAS", "emitter_freq_mhz": 2400.0},
    },
    {
        "id": str(uuid4()),
        "callsign": "NOMAD-12",
        "actor_type": "PERSON",
        "affiliation": "UNKNOWN",
        "lat": 37.8200,
        "lon": 126.7500,
        "alt": 200.0,
        "speed_mps": 1.5,
        "course_deg": 45.0,
        "source": "MESH",
        "confidence": 0.40,
        "metadata": {"detection_method": "Meshtastic LoRa", "rssi_dbm": -85},
    },
]


async def seed_via_direct_db() -> None:
    """Insert seed actors directly into PostGIS via SQLAlchemy."""
    # Import here so script works without full app install when using --api mode
    from hydra_c2.config import get_settings
    from hydra_c2.infrastructure.persistence.postgis.connection import create_engine, get_session_factory
    from hydra_c2.infrastructure.persistence.postgis.models import ActorModel
    from geoalchemy2.elements import WKTElement
    from sqlalchemy import insert, text

    settings = get_settings()
    engine = create_engine(settings.postgis.dsn)
    session_factory = get_session_factory(engine)

    print(f"[SEED] Connecting to PostGIS: {settings.postgis.host}:{settings.postgis.port}/{settings.postgis.database}")

    async with session_factory() as session:
        async with session.begin():
            # Ensure PostGIS extension
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

            for actor_data in ACTORS:
                now = datetime.now(UTC)
                # Randomize last_seen slightly for realistic timestamps
                import random

                offset_minutes = random.randint(0, 120)
                recorded_at = now - timedelta(minutes=offset_minutes)

                metadata = dict(actor_data["metadata"])
                metadata["actor_type"] = actor_data["actor_type"]
                metadata["affiliation"] = actor_data["affiliation"]
                metadata["first_seen"] = (recorded_at - timedelta(hours=random.randint(1, 48))).isoformat()

                geom = WKTElement(
                    f"POINTZ({actor_data['lon']} {actor_data['lat']} {actor_data['alt']})",
                    srid=4326,
                )

                values = {
                    "actor_id": actor_data["id"],
                    "callsign": actor_data["callsign"],
                    "team": actor_data["affiliation"],
                    "geom": geom,
                    "speed_mps": actor_data.get("speed_mps"),
                    "course_deg": actor_data.get("course_deg"),
                    "source": actor_data["source"],
                    "confidence": actor_data["confidence"],
                    "metadata": metadata,
                    "recorded_at": recorded_at,
                }

                await session.execute(insert(ActorModel).values(**values))
                print(
                    f"  [+] {actor_data['callsign']:20s}  {actor_data['affiliation']:10s}  "
                    f"{actor_data['actor_type']:20s}  ({actor_data['lat']:.4f}, {actor_data['lon']:.4f})"
                )

    await engine.dispose()
    print(f"\n[SEED] ✓ {len(ACTORS)} actors inserted successfully")


def seed_via_api(api_base: str) -> None:
    """Insert seed actors via the HYDRA-C2 REST API /api/v1/cot/ingest or direct POST.

    Since we don't have a direct POST-actor endpoint, we'll use a custom
    seed endpoint. For now we generate CoT XML and POST to /api/v1/cot/ingest.
    """
    import urllib.request
    import urllib.error

    api_base = api_base.rstrip("/")
    print(f"[SEED] Seeding via API: {api_base}")

    # For API seeding, we generate minimal CoT XML per actor
    for actor_data in ACTORS:
        cot_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<event version="2.0" uid="{actor_data["id"]}" type="a-f-G-U"
       time="{datetime.now(UTC).isoformat()}Z"
       start="{datetime.now(UTC).isoformat()}Z"
       stale="{(datetime.now(UTC) + timedelta(hours=1)).isoformat()}Z"
       how="m-g">
  <point lat="{actor_data["lat"]}" lon="{actor_data["lon"]}"
         hae="{actor_data["alt"]}" ce="35.0" le="999999.0"/>
  <detail>
    <contact callsign="{actor_data["callsign"]}"/>
    <__group name="{actor_data["affiliation"]}" role="Team Member"/>
  </detail>
</event>"""

        url = f"{api_base}/api/v1/cot/ingest"
        req = urllib.request.Request(
            url,
            data=cot_xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read())
                print(f"  [+] {actor_data['callsign']:20s}  → {body.get('status', 'ok')}")
        except urllib.error.HTTPError as e:
            print(f"  [!] {actor_data['callsign']:20s}  → HTTP {e.code}: {e.read().decode()[:100]}")
        except Exception as e:
            print(f"  [!] {actor_data['callsign']:20s}  → ERROR: {e}")

    print(f"\n[SEED] ✓ Attempted {len(ACTORS)} actors via API")


def main() -> None:
    parser = argparse.ArgumentParser(description="HYDRA-C2 Seed Data")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--api", type=str, help="Seed via REST API (e.g. http://134.199.207.172:8080)")
    group.add_argument("--direct", action="store_true", help="Seed directly into PostGIS (requires DB access)")
    args = parser.parse_args()

    if args.direct:
        asyncio.run(seed_via_direct_db())
    elif args.api:
        seed_via_api(args.api)


if __name__ == "__main__":
    main()
