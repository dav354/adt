from __future__ import annotations

from dataclasses import dataclass

DEFAULT_API_URL = "https://api.lobbyregister.bundestag.de/rest/v2"
DEFAULT_API_TIMEOUT = 30.0
DEFAULT_API_MAX_RETRIES = 3
DEFAULT_API_BACKOFF_FACTOR = 1.0
DEFAULT_API_BACKOFF_MAX = 30.0
DEFAULT_DB_CONNECT_TIMEOUT = 60.0
DEFAULT_API_KEY = "5bHB2zrUuHR6YdPoZygQhWfg2CBrjUOi"
DEFAULT_API_MAX_CONCURRENCY = 5
DEFAULT_SCHEMA_RESOURCE = "scheme-complete.json"


@dataclass(frozen=True)
class ApiConfig:
    url: str
    timeout: float
    api_key: str
    max_retries: int = DEFAULT_API_MAX_RETRIES
    backoff_factor: float = DEFAULT_API_BACKOFF_FACTOR
    backoff_max: float = DEFAULT_API_BACKOFF_MAX
    max_concurrency: int = DEFAULT_API_MAX_CONCURRENCY


@dataclass(frozen=True)
class DatabaseConfig:
    url: str
    connect_timeout: float
    apply_schema: bool = False
    schema_resource: str = DEFAULT_SCHEMA_RESOURCE


@dataclass(frozen=True)
class IngestionConfig:
    api: ApiConfig
    database: DatabaseConfig
