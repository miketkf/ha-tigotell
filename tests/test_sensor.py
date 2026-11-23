from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tigotell.const import DOMAIN
from custom_components.tigotell.sensor import (
    DESCRIPTIONS,
    TigoPanelSensor,
    async_migrate_panel_ids,
)
from tigotell_client import TigoPanel, TigoTellData


def make_panel(
    last_updated_ms=995_000,
    barcode="ABC123",
    pv_node_id=2,
    long_address=None,
):
    return TigoPanel(
        barcode=barcode,
        pv_node_id=pv_node_id,
        address=4,
        voltage_in=27.7,
        voltage_out=15.1,
        current_in=0.29,
        temperature=25.0,
        duty_cycle=42,
        rssi=80,
        last_updated_ms=last_updated_ms,
        last_seen_ms=995_100,
        long_address=long_address,
    )


def make_entity(key, panel=None, uptime_ms=1_000_000):
    coordinator = SimpleNamespace(
        data=TigoTellData("0.2.9", "fs", "build", uptime_ms, {}, (panel,) if panel else ()),
        client=SimpleNamespace(base_url="http://tigo.local:80"),
    )
    entity = object.__new__(TigoPanelSensor)
    entity._barcode = "ABC123"
    entity.entity_description = next(
        description for description in DESCRIPTIONS if description.key == key
    )
    entity.coordinator = coordinator
    return entity


def test_panel_descriptions_use_standard_home_assistant_metadata():
    assert {description.key for description in DESCRIPTIONS} == {
        "power",
        "voltage_in",
        "current_in",
        "voltage_out",
        "temperature",
        "signal_strength",
        "data_age",
    }
    assert all(
        hasattr(description, "entity_registry_enabled_default") for description in DESCRIPTIONS
    )
    assert not any(description.device_class == "timestamp" for description in DESCRIPTIONS)


def test_signal_strength_is_qualitative():
    panel = make_panel()
    entity = make_entity("signal_strength", panel)

    assert entity.native_value == "Medium"
    assert entity.entity_description.native_unit_of_measurement is None


def test_data_age_is_seconds():
    entity = make_entity("data_age", make_panel())

    assert entity.native_value == 5
    assert entity.entity_description.native_unit_of_measurement == "s"


def test_data_age_is_unknown_after_uptime_reset():
    entity = make_entity("data_age", make_panel(last_updated_ms=1_001_000))

    assert entity.native_value is None


def test_extra_state_attributes_long_address():
    entity_without = make_entity("power", make_panel())
    assert "long_address" not in entity_without.extra_state_attributes

    entity_with = make_entity("power", make_panel(long_address="04C05B4000C265A4"))
    assert entity_with.extra_state_attributes["long_address"] == "04C05B4000C265A4"


def _seed_panel_registry(
    hass,
    entry: MockConfigEntry,
    identifier: str,
    *,
    name_by_user: str | None = None,
    object_id_prefix: str | None = None,
) -> tuple[dr.DeviceEntry, dict[str, str]]:
    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    device = device_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, identifier)},
        name=f"Tigo Panel {identifier}",
    )
    if name_by_user is not None:
        device = device_reg.async_update_device(device.id, name_by_user=name_by_user)

    entity_ids: dict[str, str] = {}
    for description in DESCRIPTIONS:
        suggested = f"{object_id_prefix}_{description.key}" if object_id_prefix else None
        reg_entry = entity_reg.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{identifier}_{description.key}",
            config_entry=entry,
            device_id=device.id,
            suggested_object_id=suggested,
        )
        entity_ids[description.key] = reg_entry.entity_id
    return device, entity_ids


async def test_migrate_panel_ids_from_long_address(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "tigo.local", "port": 80})
    entry.add_to_hass(hass)

    long_address = "04C05B4000C265A4"
    barcode = "TIGO-BARCODE-01"
    old_device, old_entity_ids = _seed_panel_registry(
        hass,
        entry,
        long_address,
        name_by_user="Roof South 1",
        object_id_prefix="roof_south_1",
    )

    panel = make_panel(barcode=barcode, pv_node_id=2, long_address=long_address)
    assert async_migrate_panel_ids(hass, entry.entry_id, (panel,)) is True

    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    assert device_reg.async_get_device_by_identifier((DOMAIN, long_address), entry.entry_id) is None
    migrated_device = device_reg.async_get_device_by_identifier((DOMAIN, barcode), entry.entry_id)
    assert migrated_device is not None
    assert migrated_device.id == old_device.id
    assert migrated_device.name == f"Tigo Panel {barcode}"
    assert migrated_device.name_by_user == "Roof South 1"

    for description in DESCRIPTIONS:
        assert (
            entity_reg.async_get_entity_id("sensor", DOMAIN, f"{long_address}_{description.key}")
            is None
        )
        assert (
            entity_reg.async_get_entity_id("sensor", DOMAIN, f"{barcode}_{description.key}")
            == old_entity_ids[description.key]
        )


async def test_migrate_panel_ids_auto_repairs_simultaneous_duplicates(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "tigo.local", "port": 80})
    entry.add_to_hass(hass)

    long_address = "04C05B4000C265A4"
    node_id = "node-0002"
    barcode = "TIGO-BARCODE-01"
    old_device, old_entity_ids = _seed_panel_registry(
        hass,
        entry,
        long_address,
        name_by_user="Roof South 1",
        object_id_prefix="roof_south_1",
    )
    node_device, node_entity_ids = _seed_panel_registry(
        hass,
        entry,
        node_id,
        object_id_prefix="tigo_node_dup",
    )
    dup_device, dup_entity_ids = _seed_panel_registry(
        hass,
        entry,
        barcode,
        object_id_prefix="tigo_panel_dup",
    )

    entity_reg = er.async_get(hass)
    entity_reg.async_update_entity(
        old_entity_ids["power"], new_entity_id="sensor.my_custom_panel_power"
    )
    old_entity_ids["power"] = "sensor.my_custom_panel_power"
    entity_reg.async_update_entity(
        old_entity_ids["signal_strength"],
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    extra_entity = entity_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{barcode}_extra_custom",
        config_entry=entry,
        device_id=dup_device.id,
        suggested_object_id="tigo_panel_dup_extra",
    )

    panel = make_panel(barcode=barcode, pv_node_id=2, long_address=long_address)
    assert async_migrate_panel_ids(hass, entry.entry_id, (panel,)) is True

    device_reg = dr.async_get(hass)

    assert device_reg.async_get(node_device.id) is None
    assert device_reg.async_get(dup_device.id) is None
    assert device_reg.async_get_device_by_identifier((DOMAIN, long_address), entry.entry_id) is None
    assert device_reg.async_get_device_by_identifier((DOMAIN, node_id), entry.entry_id) is None
    migrated_device = device_reg.async_get_device_by_identifier((DOMAIN, barcode), entry.entry_id)
    assert migrated_device is not None
    assert migrated_device.id == old_device.id
    assert migrated_device.name == f"Tigo Panel {barcode}"
    assert migrated_device.name_by_user == "Roof South 1"

    for description in DESCRIPTIONS:
        assert entity_reg.async_get(node_entity_ids[description.key]) is None
        assert entity_reg.async_get(dup_entity_ids[description.key]) is None
        assert (
            entity_reg.async_get_entity_id("sensor", DOMAIN, f"{barcode}_{description.key}")
            == old_entity_ids[description.key]
        )

    custom_power = entity_reg.async_get("sensor.my_custom_panel_power")
    assert custom_power is not None
    assert custom_power.unique_id == f"{barcode}_power"
    assert custom_power.device_id == old_device.id

    disabled_signal = entity_reg.async_get(old_entity_ids["signal_strength"])
    assert disabled_signal is not None
    assert disabled_signal.unique_id == f"{barcode}_signal_strength"
    assert disabled_signal.disabled_by == er.RegistryEntryDisabler.USER

    reassigned_extra = entity_reg.async_get(extra_entity.entity_id)
    assert reassigned_extra is not None
    assert reassigned_extra.device_id == old_device.id


async def test_migrate_panel_ids_from_legacy_node_id(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "tigo.local", "port": 80})
    entry.add_to_hass(hass)

    legacy_id = "node-0002"
    barcode = "TIGO-BARCODE-02"
    old_device, old_entity_ids = _seed_panel_registry(
        hass,
        entry,
        legacy_id,
        name_by_user="Garage West 2",
        object_id_prefix="garage_west_2",
    )

    panel = make_panel(barcode=barcode, pv_node_id=2, long_address=None)
    assert async_migrate_panel_ids(hass, entry.entry_id, (panel,)) is True

    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    assert device_reg.async_get_device_by_identifier((DOMAIN, legacy_id), entry.entry_id) is None
    migrated_device = device_reg.async_get_device_by_identifier((DOMAIN, barcode), entry.entry_id)
    assert migrated_device is not None
    assert migrated_device.id == old_device.id
    assert migrated_device.name == f"Tigo Panel {barcode}"
    assert migrated_device.name_by_user == "Garage West 2"

    for description in DESCRIPTIONS:
        assert (
            entity_reg.async_get_entity_id("sensor", DOMAIN, f"{legacy_id}_{description.key}")
            is None
        )
        assert (
            entity_reg.async_get_entity_id("sensor", DOMAIN, f"{barcode}_{description.key}")
            == old_entity_ids[description.key]
        )


async def test_migrate_panel_ids_skips_downgrade_when_barcode_falls_back_to_node_id(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "tigo.local", "port": 80})
    entry.add_to_hass(hass)

    long_address = "04C05B4000C265A4"
    node_id = "node-0002"
    old_device, old_entity_ids = _seed_panel_registry(
        hass,
        entry,
        long_address,
        name_by_user="Roof South 1",
        object_id_prefix="roof_south_1",
    )

    panel = make_panel(barcode=node_id, pv_node_id=2, long_address=long_address)
    assert async_migrate_panel_ids(hass, entry.entry_id, (panel,)) is False

    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    current_device = device_reg.async_get_device_by_identifier(
        (DOMAIN, long_address), entry.entry_id
    )
    assert current_device is not None
    assert current_device.id == old_device.id
    assert device_reg.async_get_device_by_identifier((DOMAIN, node_id), entry.entry_id) is None
    for description in DESCRIPTIONS:
        assert (
            entity_reg.async_get_entity_id("sensor", DOMAIN, f"{long_address}_{description.key}")
            == old_entity_ids[description.key]
        )


async def test_migrate_panel_ids_isolated_per_config_entry(hass):
    entry_a = MockConfigEntry(domain=DOMAIN, data={"host": "tigo-a.local", "port": 80})
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain=DOMAIN, data={"host": "tigo-b.local", "port": 80})
    entry_b.add_to_hass(hass)

    long_address_a = "04C05B4000C265AA"
    barcode_a = "TIGO-BARCODE-A"
    device_a, entity_ids_a = _seed_panel_registry(
        hass,
        entry_a,
        long_address_a,
        object_id_prefix="entry_a",
    )
    device_b, entity_ids_b = _seed_panel_registry(
        hass,
        entry_b,
        "node-0002",
        name_by_user="Entry B Panel",
        object_id_prefix="entry_b",
    )

    panel_a = make_panel(barcode=barcode_a, pv_node_id=2, long_address=long_address_a)
    assert async_migrate_panel_ids(hass, entry_a.entry_id, (panel_a,)) is True

    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    # Entry A migrated to its barcode.
    migrated_a = device_reg.async_get_device_by_identifier((DOMAIN, barcode_a), entry_a.entry_id)
    assert migrated_a is not None
    assert migrated_a.id == device_a.id
    for description in DESCRIPTIONS:
        assert (
            entity_reg.async_get_entity_id("sensor", DOMAIN, f"{barcode_a}_{description.key}")
            == entity_ids_a[description.key]
        )

    # Entry B's node-0002 device and entities are untouched.
    untouched_b = device_reg.async_get_device_by_identifier((DOMAIN, "node-0002"), entry_b.entry_id)
    assert untouched_b is not None
    assert untouched_b.id == device_b.id
    assert untouched_b.name_by_user == "Entry B Panel"
    for description in DESCRIPTIONS:
        assert (
            entity_reg.async_get_entity_id("sensor", DOMAIN, f"node-0002_{description.key}")
            == entity_ids_b[description.key]
        )


async def test_migrate_panel_ids_noop_for_fresh_and_already_migrated(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "tigo.local", "port": 80})
    entry.add_to_hass(hass)

    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    # Fresh install: empty registries remain empty.
    panel = make_panel(barcode="TIGO-BARCODE-03", pv_node_id=3, long_address="04C05B4000C265FF")
    assert async_migrate_panel_ids(hass, entry.entry_id, (panel,)) is False
    assert len(device_reg.devices) == 0
    assert len(entity_reg.entities) == 0

    # Already migrated: existing canonical device and entities remain untouched.
    existing_device, existing_entity_ids = _seed_panel_registry(
        hass,
        entry,
        panel.barcode,
        name_by_user="Already Migrated",
        object_id_prefix="already_migrated",
    )
    assert async_migrate_panel_ids(hass, entry.entry_id, (panel,)) is False

    current_device = device_reg.async_get_device_by_identifier(
        (DOMAIN, panel.barcode), entry.entry_id
    )
    assert current_device is not None
    assert current_device.id == existing_device.id
    assert current_device.name_by_user == "Already Migrated"
    for description in DESCRIPTIONS:
        assert (
            entity_reg.async_get_entity_id("sensor", DOMAIN, f"{panel.barcode}_{description.key}")
            == existing_entity_ids[description.key]
        )


async def test_setup_entry_migrates_legacy_panel_on_startup(hass, enable_custom_integrations):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "tigo.local", "port": 80})
    entry.add_to_hass(hass)

    long_address = "04C05B4000C265A4"
    barcode = "TIGO-BARCODE-01"
    old_device, old_entity_ids = _seed_panel_registry(
        hass,
        entry,
        long_address,
        name_by_user="Roof South 1",
        object_id_prefix="roof_south_1",
    )
    entity_reg = er.async_get(hass)
    entity_reg.async_update_entity(
        old_entity_ids["power"], new_entity_id="sensor.my_custom_panel_power"
    )
    old_entity_ids["power"] = "sensor.my_custom_panel_power"
    entity_reg.async_update_entity(
        old_entity_ids["signal_strength"],
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    panel = make_panel(barcode=barcode, pv_node_id=2, long_address=long_address)
    snapshot = TigoTellData("0.2.9", "fs", "build", 1_000_000, {}, (panel,))

    with patch(
        "custom_components.tigotell.TigoTellClient.async_get_data",
        new=AsyncMock(return_value=snapshot),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device_reg = dr.async_get(hass)
    migrated_device = device_reg.async_get_device_by_identifier((DOMAIN, barcode), entry.entry_id)
    assert migrated_device is not None
    assert migrated_device.id == old_device.id
    assert migrated_device.name_by_user == "Roof South 1"

    power_state = hass.states.get("sensor.my_custom_panel_power")
    assert power_state is not None
    assert power_state.state == "4.38"
    assert power_state.attributes["barcode"] == barcode
    assert power_state.attributes["long_address"] == long_address

    disabled_signal = entity_reg.async_get(old_entity_ids["signal_strength"])
    assert disabled_signal is not None
    assert disabled_signal.unique_id == f"{barcode}_signal_strength"
    assert disabled_signal.disabled_by == er.RegistryEntryDisabler.USER


async def test_runtime_barcode_transition_reloads_and_migrates(hass, enable_custom_integrations):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "tigo.local", "port": 80})
    entry.add_to_hass(hass)

    initial_panel = make_panel(barcode="node-0002", pv_node_id=2, long_address=None)
    migrated_panel = make_panel(
        barcode="TIGO-BARCODE-02",
        pv_node_id=2,
        long_address="04C05B4000C265A4",
    )
    current_data = TigoTellData("0.2.9", "fs", "build", 1_000_000, {}, (initial_panel,))

    async def fake_get_data(_self):
        return current_data

    with patch("custom_components.tigotell.TigoTellClient.async_get_data", new=fake_get_data):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device_reg = dr.async_get(hass)
        entity_reg = er.async_get(hass)

        initial_device = device_reg.async_get_device_by_identifier(
            (DOMAIN, "node-0002"), entry.entry_id
        )
        assert initial_device is not None
        initial_power_id = entity_reg.async_get_entity_id("sensor", DOMAIN, "node-0002_power")
        assert initial_power_id is not None
        assert hass.states.get(initial_power_id).state == "4.38"

        current_data = TigoTellData("0.2.9", "fs", "build", 1_005_000, {}, (migrated_panel,))
        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()

    assert device_reg.async_get_device_by_identifier((DOMAIN, "node-0002"), entry.entry_id) is None
    migrated_device = device_reg.async_get_device_by_identifier(
        (DOMAIN, "TIGO-BARCODE-02"), entry.entry_id
    )
    assert migrated_device is not None
    assert migrated_device.id == initial_device.id

    assert entity_reg.async_get_entity_id("sensor", DOMAIN, "node-0002_power") is None
    assert (
        entity_reg.async_get_entity_id("sensor", DOMAIN, "TIGO-BARCODE-02_power")
        == initial_power_id
    )

    migrated_state = hass.states.get(initial_power_id)
    assert migrated_state is not None
    assert migrated_state.state == "4.38"
    assert migrated_state.attributes["barcode"] == "TIGO-BARCODE-02"
    assert migrated_state.attributes["long_address"] == "04C05B4000C265A4"
