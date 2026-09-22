import asyncio
import json
from pathlib import Path

import aiohttp
import pytest

from tigotell_client import (
    TigoTellClient,
    TigoTellConnectionError,
    TigoTellHTTPError,
    TigoTellInvalidJSONError,
    TigoTellInvalidResponseError,
)


class FakeResponse:
    def __init__(self, payload=None, error=None, status=200):
        self._payload = payload
        self._error = error
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(None, (), status=self.status)

    async def json(self):
        if self._error:
            raise self._error
        return self._payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.url = None

    def get(self, url):
        self.url = url
        if self.error:
            raise self.error
        return self.response


@pytest.mark.parametrize("port", [80, 80.0])
def test_port_is_normalized(port):
    client = TigoTellClient("tigo.local", port)

    assert client.port == 80
    assert client.base_url == "http://tigo.local:80"


@pytest.mark.parametrize("port", [0, 65536, 80.5, "not-a-port"])
def test_invalid_port_is_rejected(port):
    with pytest.raises(ValueError):
        TigoTellClient("tigo.local", port)


def test_fetches_real_seventeen_panel_snapshot():
    payload = json.loads(
        Path(__file__).with_name("fixtures").joinpath("tigotell.json").read_text(encoding="utf-8")
    )
    session = FakeSession(FakeResponse(payload))

    data = asyncio.run(TigoTellClient("tigo.local", 80, session).async_get_data())

    assert len(data.panels) == 17
    assert session.url == "http://tigo.local:80/json"


def test_invalid_json_is_not_connection_error():
    response = FakeResponse(error=json.JSONDecodeError("bad json", "{", 1))

    with pytest.raises(TigoTellInvalidJSONError):
        asyncio.run(TigoTellClient("tigo.local", session=FakeSession(response)).async_get_data())


def test_invalid_response_structure_is_not_connection_error():
    response = FakeResponse({"power": [{"pv_node_id": 1}]})

    with pytest.raises(TigoTellInvalidResponseError):
        asyncio.run(TigoTellClient("tigo.local", session=FakeSession(response)).async_get_data())


def test_non_object_response_is_invalid():
    with pytest.raises(TigoTellInvalidResponseError):
        asyncio.run(
            TigoTellClient(
                "tigo.local",
                session=FakeSession(FakeResponse(["not", "an", "object"])),
            ).async_get_data()
        )


def test_http_failure_is_distinguished():
    response = FakeResponse(status=503)

    with pytest.raises(TigoTellHTTPError):
        asyncio.run(TigoTellClient("tigo.local", session=FakeSession(response)).async_get_data())


def test_connection_failure_is_distinguished():
    session = FakeSession(error=aiohttp.ClientConnectionError("offline"))

    with pytest.raises(TigoTellConnectionError):
        asyncio.run(TigoTellClient("tigo.local", session=session).async_get_data())


def test_timeout_is_connection_error():
    response = FakeResponse(error=TimeoutError())

    with pytest.raises(TigoTellConnectionError):
        asyncio.run(TigoTellClient("tigo.local", session=FakeSession(response)).async_get_data())
