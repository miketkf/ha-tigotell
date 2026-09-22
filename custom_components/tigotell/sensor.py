"""TigoTell sensors."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from tigotell_client import TigoPanel

from . import TigoTellCoordinator, TigoTellRuntimeData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


DESCRIPTIONS = (
    SensorEntityDescription(
        key="power",
        name="Power",
        icon="mdi:solar-power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage_in",
        name="PV voltage",
        icon="mdi:flash",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="current_in",
        name="PV current",
        icon="mdi:current-dc",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage_out",
        name="Output voltage",
        icon="mdi:flash-outline",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="signal_strength",
        name="Signal strength",
        icon="mdi:signal",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="data_age",
        name="Data age",
        icon="mdi:clock-outline",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up TigoTell sensors."""
    runtime: TigoTellRuntimeData = entry.runtime_data
    coordinator = runtime.coordinator

    @callback
    def add_new_panels() -> None:
        registered_unique_ids = {
            entity.unique_id
            for entity in er.async_get(hass).entities.values()
            if entity.platform_domain == DOMAIN
        }
        new_entities = []
        for panel in coordinator.data.panels if coordinator.data else ():
            for description in DESCRIPTIONS:
                unique_id = f"{panel.barcode}_{description.key}"
                if unique_id not in registered_unique_ids:
                    new_entities.append(TigoPanelSensor(coordinator, panel.barcode, description))
        if new_entities:
            _LOGGER.debug(
                "Creating %d entities for %d TigoTell panels",
                len(new_entities),
                len(coordinator.data.panels),
            )
            async_add_entities(new_entities)

    add_new_panels()
    entry.async_on_unload(coordinator.async_add_listener(add_new_panels))

    async_add_entities([TigoTotalPowerSensor(coordinator), TigoPanelCountSensor(coordinator)])


class TigoPanelSensor(CoordinatorEntity[TigoTellCoordinator], SensorEntity):
    """A TigoTell panel measurement."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TigoTellCoordinator, barcode: str, description: SensorEntityDescription
    ) -> None:
        super().__init__(coordinator)
        self._barcode = barcode
        self.entity_description = description
        self._attr_unique_id = f"{barcode}_{description.key}"
        self._attr_name = description.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, barcode)},
            name=f"Tigo Panel {barcode}",
            manufacturer="Tigo",
            model="Tigo optimizer (via TigoTell)",
            configuration_url=f"{coordinator.client.base_url}/",
        )

    @property
    def panel(self) -> TigoPanel | None:
        """Return current panel data."""
        return (
            next((p for p in self.coordinator.data.panels if p.barcode == self._barcode), None)
            if self.coordinator.data
            else None
        )

    @property
    def available(self) -> bool:
        return super().available and self.panel is not None

    @property
    def native_value(self) -> Any:
        panel = self.panel
        if panel is None:
            return None
        match self.entity_description.key:
            case "power":
                return round(panel.power, 2)
            case "voltage_in":
                return panel.voltage_in
            case "current_in":
                return panel.current_in
            case "voltage_out":
                return panel.voltage_out
            case "temperature":
                return panel.temperature
            case "signal_strength":
                return panel.signal_strength
            case "data_age":
                uptime = self.coordinator.data.uptime_ms
                age_ms = uptime - panel.last_updated_ms
                if age_ms < 0:
                    return None
                return age_ms / 1000
            case _:
                return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        panel = self.panel
        if panel is None:
            return {}
        return {
            "barcode": panel.barcode,
            "pv_node_id": panel.pv_node_id,
            "address": panel.address,
            "raw_rssi": panel.rssi,
            "last_updated_ms": panel.last_updated_ms,
            "last_seen_ms": panel.last_seen_ms,
        }


class TigoSystemEntity(CoordinatorEntity[TigoTellCoordinator], SensorEntity):
    """Base for TigoTell system sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TigoTellCoordinator, name: str, unique_id: str, icon: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_icon = icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "system")},
            name="TigoTell",
            manufacturer="TigoTell",
            model="Tigo CCA/TAP sniffer",
            configuration_url=f"{coordinator.client.base_url}/",
        )


class TigoTotalPowerSensor(TigoSystemEntity):
    """Total instantaneous panel power."""

    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: TigoTellCoordinator) -> None:
        super().__init__(coordinator, "Total panel power", "total_panel_power", "mdi:solar-power")

    @property
    def native_value(self) -> float:
        return round(sum(panel.power for panel in self.coordinator.data.panels), 2)


class TigoPanelCountSensor(TigoSystemEntity):
    """Number of panels currently reporting power data."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "panels"

    def __init__(self, coordinator: TigoTellCoordinator) -> None:
        super().__init__(coordinator, "Reporting panels", "reporting_panels", "mdi:solar-panel")

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.panels)
