from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Mapping, Optional

import httpx

from .models import ApiConfig

LOGGER = logging.getLogger("lobbyregister.ingestor.api")


class ApiClientError(Exception):
    """Base exception for Lobbyregister API client errors."""


class ResourceNotFoundError(ApiClientError):
    """Raised when a requested resource does not exist."""


class LobbyRegisterApiClient:
    """Async HTTP client with retry and backoff logic for the Lobbyregister API."""

    def __init__(self, config: ApiConfig) -> None:
        self._config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._headers = {
            "Accept": "application/json",
            "Authorization": f"ApiKey {config.api_key}",
        }

    async def __aenter__(self) -> "LobbyRegisterApiClient":
        self._client = httpx.AsyncClient(timeout=self._config.timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_statistics(self) -> Mapping[str, Any]:
        data = await self._request_json("statistics/registerentries")
        if not isinstance(data, Mapping):
            raise ApiClientError("Statistics endpoint returned unexpected payload")
        return data

    async def iter_register_entries(
        self, query: Optional[str] = None
    ) -> AsyncIterator[Mapping[str, Any]]:
        cursor: Optional[str] = None
        seen_cursors: set[str] = set()
        while True:
            params: dict[str, Any] = {"format": "json"}
            if query:
                params["q"] = query
            if cursor:
                params["cursor"] = cursor

            payload = await self._request_json("registerentries", params=params)
            metadata = {
                "source": payload.get("source"),
                "sourceUrl": payload.get("sourceUrl"),
                "sourceDate": payload.get("sourceDate"),
                "jsonDocumentationUrl": payload.get("jsonDocumentationUrl"),
            }
            entries = self._extract_entries(payload)
            for entry in entries:
                entry.update(metadata)
                yield entry

            next_cursor = (
                payload.get("cursor") if isinstance(payload, Mapping) else None
            )
            if not isinstance(next_cursor, str):
                break
            if next_cursor == cursor or next_cursor in seen_cursors:
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor

    async def get_register_entry_version(
        self, register_number: str, version: int
    ) -> Mapping[str, Any]:
        payload = await self._request_json(
            f"registerentries/{register_number}/{version}"
        )
        if not isinstance(payload, Mapping):
            raise ApiClientError(
                f"Register entry version {register_number}/{version} returned unexpected payload"
            )
        return payload

    async def get_register_entry(self, register_number: str) -> Mapping[str, Any]:
        payload = await self._request_json(f"registerentries/{register_number}")
        if not isinstance(payload, Mapping):
            raise ApiClientError(
                f"Register entry {register_number} returned unexpected payload"
            )
        return payload

    async def _request_json(
        self, path: str, params: Optional[Mapping[str, Any]] = None
    ) -> Any:
        if self._client is None:
            raise RuntimeError("HTTP client is not ready")

        url = f"{self._config.url.rstrip('/')}/{path.lstrip('/')}"
        params_dict = dict(params or {})
        max_attempts = max(1, self._config.max_retries + 1)
        base_backoff = max(self._config.backoff_factor, 0.0) or 1.0
        backoff_ceiling = (
            self._config.backoff_max
            if self._config.backoff_max and self._config.backoff_max > 0
            else float("inf")
        )
        sleep_time = base_backoff

        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            try:
                LOGGER.debug(
                    "Requesting %s (attempt %s/%s)", url, attempt, max_attempts
                )
                response = await self._client.get(
                    url,
                    headers=self._headers,
                    params=params_dict,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code == 404:
                    payload_preview = exc.response.text[:500]
                    LOGGER.warning(
                        "Resource not found at %s (preview: %s)", url, payload_preview
                    )
                    raise ResourceNotFoundError(str(exc)) from exc

                retryable_status = status_code >= 500 or status_code in {408, 429}
                if not self._should_retry(attempt, max_attempts, retryable_status):
                    payload_preview = exc.response.text[:500]
                    LOGGER.error(
                        "HTTP %s for %s; response preview: %s",
                        status_code,
                        url,
                        payload_preview,
                    )
                    raise
                wait_time = min(sleep_time, backoff_ceiling)
                LOGGER.warning(
                    "HTTP %s for %s (attempt %s/%s). Retrying in %.1fs",
                    status_code,
                    url,
                    attempt,
                    max_attempts,
                    wait_time,
                )
                await asyncio.sleep(wait_time)
                sleep_time = self._next_backoff(
                    sleep_time, base_backoff, backoff_ceiling
                )
            except httpx.RequestError as exc:
                if not self._should_retry(attempt, max_attempts, True):
                    raise
                wait_time = min(sleep_time, backoff_ceiling)
                LOGGER.warning(
                    "Network error for %s (attempt %s/%s): %s. Retrying in %.1fs",
                    url,
                    attempt,
                    max_attempts,
                    exc,
                    wait_time,
                )
                await asyncio.sleep(wait_time)
                sleep_time = self._next_backoff(
                    sleep_time, base_backoff, backoff_ceiling
                )

        raise ApiClientError(f"Failed to fetch {url} after {max_attempts} attempts")

    @staticmethod
    def _should_retry(attempt: int, max_attempts: int, retryable: bool) -> bool:
        return retryable and attempt < max_attempts

    @staticmethod
    def _next_backoff(current: float, base: float, ceiling: float) -> float:
        next_value = max(current, base) * 2
        if ceiling > 0:
            next_value = min(next_value, ceiling)
        return max(next_value, base)

    @staticmethod
    def _extract_entries(payload: Any) -> list[Mapping[str, Any]]:
        if isinstance(payload, Mapping):
            entries_obj = payload.get("results") or payload.get("registerEntries")
            if isinstance(entries_obj, list):
                return [entry for entry in entries_obj if isinstance(entry, Mapping)]
            if "registerNumber" in payload:
                return [payload]
        elif isinstance(payload, list):
            return [entry for entry in payload if isinstance(entry, Mapping)]

        preview = str(payload)
        if len(preview) > 500:
            preview = preview[:500] + "…"
        raise ApiClientError(
            f"Register entries endpoint returned unexpected payload: {preview}"
        )
