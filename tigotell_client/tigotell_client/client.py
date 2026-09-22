"""HTTP client for TigoTell."""

from __future__ import annotations

from typing import Any

import aiohttp

from .models import TigoTellData, parse_snapshot


class TigoTellError(Exception):
    """Base TigoTell exception."""


class TigoTellConnectionError(TigoTellError):
    """Raised when TigoTell cannot be reached or returns invalid data."""


class TigoTellClient:
    """Small async client for the TigoTell REST API."""

    def __init__(
        self,
        host: str,
        port: int = 80,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._session = session
        self._owns_session = session is None

    @property
    def base_url(self) -> str:
        """Return the TigoTell base URL."""
        return f"http://{self._host}:{self._port}"

    async def async_get_data(self) -> TigoTellData:
        """Fetch and parse /json."""
        session = self._session
        if session is None:
            timeout = aiohttp.ClientTimeout(total=10)
            session = aiohttp.ClientSession(timeout=timeout)
        try:
            async with session.get(f"{self.base_url}/json") as response:
                response.raise_for_status()
                payload: dict[str, Any] = await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise TigoTellConnectionError(str(err)) from err
        finally:
            if self._owns_session:
                await session.close()
        try:
            return parse_snapshot(payload)
        except (KeyError, TypeError, ValueError) as err:
            raise TigoTellError(f"Invalid TigoTell /json response: {err}") from err
