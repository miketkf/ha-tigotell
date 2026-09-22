"""TigoTell sensors."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_category import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from tigotell_client import TigoPanel
from . import TigoTellCoordinator, TigoTellRuntimeData
from .const import DOMAIN

@dataclass(frozen=True, slots=True)
class PanelSensorDescription:
    key: str
    name: str
    icon: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    diagnostic: bool = False

DESCRIPTIONS = (
    PanelSensorDescription("power", "Power", "mdi:solar-power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    PanelSensorDescription("voltage_in", "PV voltage", "mdi:flash", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    PanelSensorDescription("current_in", "PV current", "mdi:current-dc", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    PanelSensorDescription("voltage_out", "Output voltage", "mdi:flash-outline", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    PanelSensorDescription("temperature", "Temperature", "mdi:thermometer", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    PanelSensorDescription("signal_strength", "Signal strength", "mdi:signal", diagnostic=True),
    PanelSensorDescription("last_update", "Last update", "mdi:clock-outline", device_class=SensorDeviceClass.TIMESTAMP, diagnostic=True),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable) -> None:
    """Set up TigoTell sensors."""
    runtime: TigoTellRuntimeData = entry.runtime_data
    coordinator = runtime.coordinator
    known: set[tuple[str, str]] = set()

    @callback
    def add_new_panels() -> None:
        new_entities = []
        for panel in coordinator.data.panels if coordinator.data else ():
            for description in DESCRIPTIONS:
                key = (panel.barcode, description.key)
                if key not in known:
                    known.add(key)
                    new_entities.append(TigoPanelSensor(coordinator, panel.barcode, description))
        if new_entities:
            async_add_entities(new_entities)

    add_new_panels()
    entry.async_on_unload(coordinator.async_add_listener(add_new_panels))

    async_add_entities([TigoTotalPowerSensor(coordinator), TigoPanelCountSensor(coordinator)])

class TigoPanelSensor(CoordinatorEntity[TigoTellCoordinator], SensorEntity):
    """A TigoTell panel measurement."""
    _attr_has_entity_name = True

    def __init__(self, coordinator: TigoTellCoordinator, barcode: str, description: PanelSensorDescription) -> None:
        super().__init__(coordinator)
        self._barcode = barcode
        self.entity_description = description
        self._attr_unique_id = f"{barcode}_{description.key}"
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_native_unit_of_measurement = description.unit
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        if description.diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
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
        return next((p for p in self.coordinator.data.panels if p.barcode == self._barcode), None) if self.coordinator.data else None

    @property
    def available(self) -> bool:
        return super().available and self.panel is not None

    @property
    def native_value(self) -> Any:
        panel = self.panel
        if panel is None:
            return None
        match self.entity_description.key:
            case "power": return round(panel.power, 2)
            case "voltage_in": return panel.voltage_in
            case "current_in": return panel.current_in
            case "voltage_out": return panel.voltage_out
            case "temperature": return panel.temperature
            case "signal_strength": return panel.signal_strength
            case "last_update":
                uptime = self.coordinator.data.uptime_ms
                age_ms = uptime - panel.last_updated_ms
                if age_ms < 0:
                    return None
                return datetime.now(timezone.utc) - timedelta(milliseconds=age_ms)
            case _: return None

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

    def __init__(self, coordinator: TigoTellCoordinator, name: str, unique_id: str, icon: str) -> None:
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
