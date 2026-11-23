import json
from pathlib import Path

from tigotell_client.models import parse_snapshot


def test_parse_real_tigotell_snapshot():
    payload = json.loads(Path(__file__).with_name("fixtures").joinpath("tigotell.json").read_text())
    data = parse_snapshot(payload)
    assert len(data.panels) == 17
    panel = next(p for p in data.panels if p.pv_node_id == 2)
    assert panel.barcode == "04C05B4000C265A4"
    assert panel.voltage_in == 27.7
    assert panel.voltage_out == 15.1
    assert panel.current_in == 0.29
    assert panel.power == 4.379
    assert panel.signal_strength == "Medium"
    assert panel.last_updated_ms == 174485168
    assert panel.long_address is None
    assert data.uptime_ms == 174485389


def test_parse_snapshot_long_address():
    base_power = {
        "address": 123,
        "pv_node_id": 2,
        "voltage_in": 27.7,
        "voltage_out": 15.1,
        "current_in": 0.29,
        "temperature": 28,
        "duty_cycle": 143,
        "rssi": 105,
        "last_updated": 174485168,
    }
    with_long_addr = parse_snapshot(
        {
            "power": [base_power],
            "nodes": [
                {
                    "pv_node_id": 2,
                    "barcode": "A1B2C3D4",
                    "long_address": "04C05B4000C265A4",
                }
            ],
        }
    )
    assert with_long_addr.panels[0].barcode == "A1B2C3D4"
    assert with_long_addr.panels[0].long_address == "04C05B4000C265A4"

    without_long_addr = parse_snapshot(
        {
            "power": [base_power],
            "nodes": [{"pv_node_id": 2, "barcode": "A1B2C3D4"}],
        }
    )
    assert without_long_addr.panels[0].long_address is None

    empty_long_addr = parse_snapshot(
        {
            "power": [base_power],
            "nodes": [{"pv_node_id": 2, "barcode": "A1B2C3D4", "long_address": ""}],
        }
    )
    assert empty_long_addr.panels[0].long_address is None

    none_long_addr = parse_snapshot(
        {
            "power": [base_power],
            "nodes": [{"pv_node_id": 2, "barcode": "A1B2C3D4", "long_address": None}],
        }
    )
    assert none_long_addr.panels[0].long_address is None
