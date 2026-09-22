"""TigoTell Home Assistant integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from tigotell_client import TigoTellClient, TigoTellConnectionError, TigoTellData

from .const import CONF_HOST, CONF_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

@dataclass(slots=True)
class TigoTellRuntimeData:
    """Runtime data for a config entry."""
    client: TigoTellClient
    coordinator: "TigoTellCoordinator"

class TigoTellCoordinator(DataUpdateCoordinator[TigoTellData]):
    """Fetch TigoTell snapshots."""

    def __init__(self, hass: HomeAssistant, client: TigoTellClient) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> TigoTellData:
        try:
            return await self.client.async_get_data()
        except TigoTellConnectionError as err:
            raise UpdateFailed(str(err)) from err

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TigoTell from a config entry."""
    session = async_get_clientsession(hass)
    client = TigoTellClient(entry.data[CONF_HOST], entry.data[CONF_PORT], session)
    coordinator = TigoTellCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = TigoTellRuntimeData(client, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload TigoTell."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
