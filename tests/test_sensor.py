from types import SimpleNamespace

from custom_components.tigotell.sensor import DESCRIPTIONS, TigoPanelSensor
from tigotell_client import TigoPanel, TigoTellData


def make_panel(last_updated_ms=995_000):
    return TigoPanel(
        barcode="ABC123",
        pv_node_id=2,
        address=4,
        voltage_in=27.7,
        voltage_out=15.1,
        current_in=0.29,
        temperature=25.0,
        duty_cycle=42,
        rssi=80,
        last_updated_ms=last_updated_ms,
        last_seen_ms=995_100,
    )


def make_entity(key, panel=None, uptime_ms=1_000_000):
    coordinator = SimpleNamespace(
        data=TigoTellData("0.2.9", "fs", "build", uptime_ms, {}, (panel,) if panel else ()),
        client=SimpleNamespace(base_url="http://tigo.local:80"),
    )
    entity = object.__new__(TigoPanelSensor)
    entity._barcode = "ABC123"
    entity.entity_description = next(description for description in DESCRIPTIONS if description.key == key)
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
    assert all(hasattr(description, "entity_registry_enabled_default") for description in DESCRIPTIONS)
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
