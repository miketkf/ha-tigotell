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
    assert data.uptime_ms == 174485389
