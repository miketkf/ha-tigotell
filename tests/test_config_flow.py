from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from custom_components.tigotell.const import CONF_PORT, DOMAIN
from tigotell_client import TigoTellInvalidResponseError


@pytest.mark.parametrize("port", [80, 80.0])
async def test_config_flow_normalizes_port(hass, enable_custom_integrations, port):
    with patch(
        "custom_components.tigotell.config_flow.TigoTellClient.async_get_data",
        new=AsyncMock(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "tigo.local", CONF_PORT: port},
        )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_PORT] == 80


async def test_config_flow_maps_invalid_response(hass, enable_custom_integrations):
    with patch(
        "custom_components.tigotell.config_flow.TigoTellClient.async_get_data",
        new=AsyncMock(side_effect=TigoTellInvalidResponseError("bad data")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "tigo.local", CONF_PORT: 80},
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_response"}


async def test_config_flow_logs_unexpected_error(hass, enable_custom_integrations, caplog):
    with patch(
        "custom_components.tigotell.config_flow.TigoTellClient.async_get_data",
        new=AsyncMock(side_effect=RuntimeError("unexpected")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "tigo.local", CONF_PORT: 80},
        )

    assert result["errors"] == {"base": "invalid_response"}
    assert "Unexpected error validating TigoTell" in caplog.text
