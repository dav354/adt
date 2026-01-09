"""Async HTTP client for the Bundestag lobby register API."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx

from .config import Settings
from .logging_utils import get_logger

logger = get_logger(__name__)


class ApiError(Exception):
    """Raised when the Lobbyregister API cannot fulfill a request."""


class ResourceNotFoundError(ApiError):
    """Raised when a requested resource does not exist."""


class LobbyregisterClient:
    """Async client that pages through register entries via the cursor API."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: httpx.AsyncClient | None = None
        self._headers = {
            "Accept": "application/json",
            "User-Agent": "lobbyregister-ingestor/1.0",
        }
        if settings.api_key:
            self._headers["X-API-Key"] = settings.api_key
            self._headers["Authorization"] = f"ApiKey {settings.api_key}"

    async def __aenter__(self) -> LobbyregisterClient:
        limits = httpx.Limits(
            max_connections=self._settings.http_concurrency,
            max_keepalive_connections=self._settings.http_concurrency,
        )
        self._client = httpx.AsyncClient(
            timeout=self._settings.http_timeout,
            limits=limits,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_statistics(self) -> Mapping[str, Any]:
        payload = await self._request_json("statistics/registerentries")
        if not isinstance(payload, Mapping):
            raise ApiError("Statistics endpoint returned unexpected payload")
        return payload

    async def iter_register_entries(
        self, query: str | None = None
    ) -> AsyncIterator[Mapping[str, Any]]:
        stop_token = object()
        queue: asyncio.Queue = asyncio.Queue(
            maxsize=max(1, self._settings.http_concurrency)
        )
        fetch_error: BaseException | None = None

        async def fetch_pages() -> None:
            nonlocal fetch_error
            base_params: dict[str, Any] = {"format": "json"}
            if query:
                base_params["q"] = query

            cursor: str | None = None
            seen_cursors: set[str] = set()

            try:
                while True:
                    params = dict(base_params)
                    if cursor:
                        params["cursor"] = cursor

                    payload = await self._request_json("registerentries", params=params)
                    metadata = {
                        "source": payload.get("source"),
                        "sourceUrl": payload.get("sourceUrl"),
                        "sourceDate": payload.get("sourceDate"),
                        "jsonDocumentationUrl": payload.get("jsonDocumentationUrl"),
                        "resultCount": payload.get("resultCount"),
                        "totalResultCount": payload.get("totalResultCount"),
                    }
                    entries = self._extract_entries(payload)
                    await queue.put((entries, metadata))

                    next_cursor = (
                        payload.get("cursor") if isinstance(payload, Mapping) else None
                    )
                    if not isinstance(next_cursor, str):
                        break
                    if next_cursor == cursor or next_cursor in seen_cursors:
                        break
                    seen_cursors.add(next_cursor)
                    cursor = next_cursor
            except BaseException as exc:
                fetch_error = exc
            finally:
                await queue.put((stop_token, None))

        fetch_task = asyncio.create_task(fetch_pages())

        try:
            while True:
                entries, metadata = await queue.get()
                queue.task_done()
                if entries is stop_token:
                    break

                metadata = metadata or {}
                for entry in entries:
                    merged = dict(entry)
                    merged.update({k: v for k, v in metadata.items() if v is not None})
                    yield merged
        finally:
            if not fetch_task.done():
                fetch_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await fetch_task
            else:
                await fetch_task

        if fetch_error:
            raise fetch_error

    async def get_register_entry(self, register_number: str) -> Mapping[str, Any]:
        payload = await self._request_json(f"registerentries/{register_number}")
        if not isinstance(payload, Mapping):
            raise ApiError(
                f"Register entry {register_number} returned unexpected payload"
            )
        return payload

    async def _request_json(
        self, path: str, params: Mapping[str, Any] | None = None
    ) -> Any:
        if self._client is None:
            raise RuntimeError("HTTP client is not ready")

        base_url = self._settings.api_base.rstrip("/")
        url = f"{base_url}/{path.lstrip('/')}"
        params_dict = dict(params or {})
        max_attempts = max(1, self._settings.http_max_retries + 1)
        base_backoff = max(self._settings.http_backoff_factor, 0.0) or 1.0
        backoff_ceiling = (
            self._settings.http_backoff_max
            if self._settings.http_backoff_max > 0
            else float("inf")
        )
        sleep_time = base_backoff
        attempt = 0

        while attempt < max_attempts:
            attempt += 1
            try:
                logger.debug(
                    "Requesting %s (attempt %s/%s)", url, attempt, max_attempts
                )
                response = await self._client.get(
                    url, headers=self._headers, params=params_dict
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                preview = exc.response.text[:500]
                if status_code == 404:
                    logger.warning(
                        "Resource not found at %s (preview: %s)", url, preview
                    )
                    raise ResourceNotFoundError(str(exc)) from exc

                retryable = status_code >= 500 or status_code in {408, 429}
                if not self._should_retry(attempt, max_attempts, retryable):
                    logger.error(
                        "HTTP %s for %s; response preview: %s",
                        status_code,
                        url,
                        preview,
                    )
                    message = f"HTTP {status_code} for {url}"
                    if preview:
                        message += f"; response preview: {preview}"
                    raise ApiError(message) from exc
                wait_time = min(sleep_time, backoff_ceiling)
                logger.warning(
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
                    raise ApiError(f"Network error for {url}: {exc}") from exc
                wait_time = min(sleep_time, backoff_ceiling)
                logger.warning(
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

        raise ApiError(f"Failed to fetch {url} after {max_attempts} attempts")

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
            if entries_obj is None and payload.get("resultCount") in (0, "0"):
                return []
            if (
                entries_obj is None
                and not payload.get("results")
                and not payload.get("registerEntries")
            ):
                # Some responses (e.g., empty search snapshots) omit the usual lists.
                return []
            if "registerNumber" in payload:
                return [payload]
        elif isinstance(payload, list):
            return [entry for entry in payload if isinstance(entry, Mapping)]

        preview = str(payload)
        if len(preview) > 500:
            preview = preview[:500] + "…"
        raise ApiError(
            f"Register entries endpoint returned unexpected payload: {preview}"
        )
