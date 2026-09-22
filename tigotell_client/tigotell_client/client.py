"""HTTP client for TigoTell."""

from __future__ import annotations

import json
from typing import Any

import aiohttp

from .models import TigoTellData, parse_snapshot


class TigoTellError(Exception):
    """Base TigoTell exception."""


class TigoTellConnectionError(TigoTellError):
    """Raised when TigoTell cannot be reached."""


class TigoTellHTTPError(TigoTellConnectionError):
    """Raised when TigoTell returns an HTTP error response."""


class TigoTellInvalidJSONError(TigoTellError):
    """Raised when TigoTell returns malformed JSON."""


class TigoTellInvalidResponseError(TigoTellError):
    """Raised when TigoTell returns JSON with an invalid structure."""


class TigoTellClient:
    """Small async client for the TigoTell REST API."""

    def __init__(
        self,
        host: str,
        port: int | float = 80,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        if isinstance(port, bool):
            raise ValueError("port must be an integer between 1 and 65535")
        try:
            normalized_port = int(port)
        except (TypeError, ValueError, OverflowError) as err:
            raise ValueError("port must be an integer between 1 and 65535") from err
        if normalized_port != port or not 1 <= normalized_port <= 65535:
            raise ValueError("port must be an integer between 1 and 65535")
        self._host = host
        self._port = normalized_port
        self._session = session
        self._owns_session = session is None

    @property
    def base_url(self) -> str:
        """Return the TigoTell base URL."""
        return f"http://{self._host}:{self._port}"

    @property
    def port(self) -> int:
        """Return the normalized HTTP port."""
        return self._port

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
        except TimeoutError as err:
            raise TigoTellConnectionError("TigoTell request timed out") from err
        except (aiohttp.ContentTypeError, json.JSONDecodeError, UnicodeDecodeError) as err:
            raise TigoTellInvalidJSONError("TigoTell returned invalid JSON") from err
        except aiohttp.ClientConnectionError as err:
            raise TigoTellConnectionError(str(err)) from err
        except aiohttp.ClientResponseError as err:
            raise TigoTellHTTPError(f"TigoTell returned HTTP {err.status}") from err
        finally:
            if self._owns_session:
                await session.close()
        try:
            return parse_snapshot(payload)
        except (KeyError, TypeError, ValueError) as err:
            raise TigoTellInvalidResponseError(f"Invalid TigoTell /json response: {err}") from err
