"""HYDRA-C2 Configuration — Environment-based settings.

All secrets loaded from environment variables.
Supports: .env file, Docker Compose env, K8s secrets.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class PostGISSettings(BaseSettings):
    """PostgreSQL/PostGIS connection settings."""

    host: str = "localhost"
    port: int = 5432
    database: str = "hydra_c2"
    user: str = "hydra"
    password: str = "hydra_dev_2026"

    model_config = {"env_prefix": "POSTGIS_"}

    @property
    def dsn(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class Neo4jSettings(BaseSettings):
    """Neo4j connection settings."""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "hydra_graph_2026"

    model_config = {"env_prefix": "NEO4J_"}


class MqttSettings(BaseSettings):
    """MQTT broker connection settings."""

    host: str = "localhost"
    port: int = 1883
    ws_port: int = 9001

    model_config = {"env_prefix": "MQTT_"}


class TakSettings(BaseSettings):
    """TAK Server connection settings."""

    host: str = "localhost"
    port: int = 8089
    protocol: str = "tcp"  # tcp | ssl | udp
    cert_path: str = ""
    key_path: str = ""

    model_config = {"env_prefix": "TAK_"}


class Settings(BaseSettings):
    """Root settings aggregator."""

    app_name: str = "HYDRA-C2"
    version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    postgis: PostGISSettings = PostGISSettings()
    neo4j: Neo4jSettings = Neo4jSettings()
    mqtt: MqttSettings = MqttSettings()
    tak: TakSettings = TakSettings()

    # DO GPU Cloud (for analytics offload)
    do_gpu_host: str = "134.199.207.172"
    do_gpu_ssh_user: str = "root"

    model_config = {"env_prefix": "HYDRA_"}


def get_settings() -> Settings:
    """Factory function for settings singleton."""
    return Settings()
