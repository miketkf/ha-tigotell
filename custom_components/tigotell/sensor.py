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
from homeassistant.helpers import device_registry as dr
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
        entity_registry_enabled_default=True,
        suggested_display_precision=0,
    ),
)


@callback
def async_migrate_panel_ids(
    hass: HomeAssistant,
    config_entry_id: str,
    panels: tuple[TigoPanel, ...],
) -> bool:
    """Migrate legacy panel unique IDs and device identifiers to canonical barcodes."""
    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)
    migrated = False

    for panel in panels:
        node_id = f"node-{panel.pv_node_id:04d}"
        if panel.barcode == node_id:
            continue

        legacy_ids: list[str] = []
        if panel.long_address and panel.long_address not in (panel.barcode, node_id):
            legacy_ids.append(panel.long_address)
        legacy_ids.append(node_id)
        candidates = [*legacy_ids, panel.barcode]

        for description in DESCRIPTIONS:
            matched: list[tuple[str, er.RegistryEntry]] = []
            for cand in candidates:
                ent_id = entity_reg.async_get_entity_id(
                    "sensor", DOMAIN, f"{cand}_{description.key}"
                )
                if ent_id is None:
                    continue
                ent_entry = entity_reg.async_get(ent_id)
                if ent_entry is not None and ent_entry.config_entry_id == config_entry_id:
                    matched.append((cand, ent_entry))

            if not matched:
                continue

            winner_cand, winner_entry = matched[0]
            if winner_cand == panel.barcode and len(matched) == 1:
                continue

            for _, dup_entry in matched[1:]:
                entity_reg.async_remove(dup_entry.entity_id)
                migrated = True

            if winner_cand != panel.barcode:
                entity_reg.async_update_entity(
                    winner_entry.entity_id,
                    new_unique_id=f"{panel.barcode}_{description.key}",
                )
                migrated = True

        matched_devices: list[tuple[str, dr.DeviceEntry]] = []
        seen_device_ids: set[str] = set()
        for cand in candidates:
            dev = device_reg.async_get_device_by_identifier((DOMAIN, cand), config_entry_id)
            if dev is not None and dev.id not in seen_device_ids:
                seen_device_ids.add(dev.id)
                matched_devices.append((cand, dev))

        if matched_devices:
            winner_cand, winner_device = matched_devices[0]
            for _, dup_device in matched_devices[1:]:
                for entity_entry in er.async_entries_for_device(
                    entity_reg, dup_device.id, include_disabled_entities=True
                ):
                    if entity_entry.config_entry_id == config_entry_id:
                        entity_reg.async_update_entity(
                            entity_entry.entity_id, device_id=winner_device.id
                        )
                device_reg.async_remove_device(dup_device.id)
                migrated = True

            if winner_cand != panel.barcode:
                device_reg.async_update_device(
                    winner_device.id,
                    new_identifiers={(DOMAIN, panel.barcode)},
                    name=f"Tigo Panel {panel.barcode}",
                )
                migrated = True

    return migrated


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up TigoTell sensors."""
    runtime: TigoTellRuntimeData = entry.runtime_data
    coordinator = runtime.coordinator
    known: set[tuple[str, str]] = set()
    checked_panels: set[tuple[str, str | None, int]] = set()
    reloading = False

    @callback
    def add_new_panels() -> None:
        """Add entities for newly discovered panels."""
        nonlocal reloading
        if not coordinator.data or reloading:
            return

        unchecked = tuple(
            p
            for p in coordinator.data.panels
            if (p.barcode, p.long_address, p.pv_node_id) not in checked_panels
        )
        if unchecked:
            had_known = bool(known)
            migrated = async_migrate_panel_ids(hass, entry.entry_id, unchecked)
            if migrated and had_known:
                reloading = True
                hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
                return
            for p in unchecked:
                checked_panels.add((p.barcode, p.long_address, p.pv_node_id))

        new_entities = []

        for panel in coordinator.data.panels:
            for description in DESCRIPTIONS:
                key = (panel.barcode, description.key)

                if key in known:
                    continue

                new_entities.append(TigoPanelSensor(coordinator, panel.barcode, description))
                known.add(key)

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
        self,
        coordinator: TigoTellCoordinator,
        barcode: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a panel sensor."""
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
            next(
                (p for p in self.coordinator.data.panels if p.barcode == self._barcode),
                None,
            )
            if self.coordinator.data
            else None
        )

    @property
    def available(self) -> bool:
        """Return whether the panel has current data."""
        return super().available and self.panel is not None

    @property
    def native_value(self) -> Any:
        """Return the current sensor value."""
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
        """Return diagnostic panel attributes."""
        panel = self.panel
        if panel is None:
            return {}

        attrs: dict[str, Any] = {
            "barcode": panel.barcode,
            "pv_node_id": panel.pv_node_id,
            "address": panel.address,
            "raw_rssi": panel.rssi,
            "last_updated_ms": panel.last_updated_ms,
            "last_seen_ms": panel.last_seen_ms,
        }
        if panel.long_address is not None:
            attrs["long_address"] = panel.long_address
        return attrs


class TigoSystemEntity(CoordinatorEntity[TigoTellCoordinator], SensorEntity):
    """Base for TigoTell system sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TigoTellCoordinator, name: str, unique_id: str, icon: str
    ) -> None:
        """Initialize a system sensor."""
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
        """Initialize the total power sensor."""
        super().__init__(coordinator, "Total panel power", "total_panel_power", "mdi:solar-power")

    @property
    def native_value(self) -> float:
        """Return total instantaneous panel power."""
        return round(sum(panel.power for panel in self.coordinator.data.panels), 2)


class TigoPanelCountSensor(TigoSystemEntity):
    """Number of panels currently reporting power data."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "panels"

    def __init__(self, coordinator: TigoTellCoordinator) -> None:
        """Initialize the panel count sensor."""
        super().__init__(coordinator, "Reporting panels", "reporting_panels", "mdi:solar-panel")

    @property
    def native_value(self) -> int:
        """Return number of reporting panels."""
        return len(self.coordinator.data.panels)
