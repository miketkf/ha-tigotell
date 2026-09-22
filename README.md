# TigoTell for Home Assistant

A community Home Assistant integration for [gongloo/TigoTell](https://github.com/gongloo/TigoTell).

TigoTell passively decodes Tigo CCA/TAP traffic and exposes a local `/json` endpoint containing the latest module telemetry. This integration polls that endpoint and presents the current panel data directly in Home Assistant. It does **not** require MQTT, InfluxDB, Telegraf, or another translation service.

## Credits

This project depends on and is built around the excellent open-source [TigoTell](https://github.com/gongloo/TigoTell) project by **gongloo**. TigoTell's own README credits [willglynn/taptap](https://github.com/willglynn/taptap) and [tictactom/tigo_server](https://github.com/tictactom/tigo_server) for the reverse-engineering work behind the protocol decoding. Please support and credit those upstream projects when redistributing this integration.

TigoTell is MIT licensed; see the upstream repository for its license and attribution details.

## What it provides

Each discovered panel/optimizer becomes a Home Assistant device. The stable device identifier is the Tigo barcode. Current entities are:

- **Power** — calculated as `voltage_out × current_in`, matching TigoTell's own Influx line-protocol calculation.
- **PV voltage** — `voltage_in`.
- **PV current** — `current_in`.
- **Output voltage** — `voltage_out`.
- **Temperature** — `temperature`.
- **Signal strength** — qualitative High/Medium/Low. The raw Tigo RSSI value is retained as a diagnostic attribute rather than being incorrectly labelled dBm.
- **Last update** — an estimated wall-clock timestamp derived from TigoTell's monotonic uptime counters.

Duty cycle is intentionally not exposed as a normal entity. The raw Tigo node ID, address, RSSI, and TigoTell uptime counters are retained as diagnostic attributes.

The integration also exposes **Total panel power** and **Reporting panels** on a TigoTell system device.

## Panel names / aliases

The barcode remains the stable identifier, but users do not have to live with barcode-based names. Home Assistant's device registry allows the panel device to be renamed from the device page. Renaming changes the user-facing device/entity names while the integration keeps the barcode as the stable identifier. This is the recommended way to give panels friendly names such as `Garage West`, `Roof South 1`, etc.

## Installation

### HACS

The integration is designed to be installed as a custom HACS repository until it is accepted into the normal HACS/default repository flow.

1. In Home Assistant open **HACS → Integrations**.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add the GitHub repository URL for this project.
4. Select **Integration** as the category.
5. Install **TigoTell**.
6. Restart Home Assistant.
7. Go to **Settings → Devices & services → Add integration**.
8. Select **TigoTell**.
9. Enter the TigoTell hostname/IP and HTTP port (normally `80`).

The config flow tests `/json` before creating the entry.

### PyPI dependency

The HA integration uses the small `tigotell-client` package for communication with TigoTell. This follows Home Assistant's current integration architecture for external-device communication. The package is published separately to PyPI and is installed automatically by Home Assistant from the integration's `manifest.json` dependency.

Before publishing this repository, publish `tigotell_client/` as `tigotell-client` version `0.1.0` to PyPI, then keep the matching requirement in `manifest.json`.

## Polling

The default polling interval is 10 seconds. TigoTell itself controls how often it receives and stores frames; the integration only reads the latest snapshot. No history database is required.

## Dashboard examples

Two dashboard examples are included under `examples/`.

### Recommended overview

`examples/dashboard-tigotell-overview.yaml` is a simple responsive dashboard using built-in Home Assistant cards. It shows total current power and all panel power values.

### Taptap-style dashboard

`examples/dashboard-tigotell-taptap-style.yaml` adapts the supplied taptap dashboard pattern: four-column responsive panel power gauges plus a second section showing each panel's last-update time. The original dashboard used 17 panels, so this example is populated for the 17 panels present in the supplied TigoTell snapshot. The original layout's mobile/desktop behavior is retained.

The original dashboard used per-panel power and timestamp sensors plus overall daily energy and total power badges. TigoTell's `/json` endpoint does not expose accumulated daily energy, so the adapted dashboard uses **Total panel power** and **Reporting panels** instead. Add a separate inverter/energy integration if daily energy is required.

### Creating your own dashboard

1. Create a new dashboard in **Settings → Dashboards**.
2. Add a **Sections** view.
3. Add cards for the panel Power entities.
4. Use the panel's friendly device name after renaming it in the device registry.
5. The example YAML can be pasted into the dashboard's raw configuration editor and then adjusted to your panel names/entities.

## Development

The project uses:

- Python 3.12+
- Home Assistant 2026.9+
- `pytest`
- `pytest-homeassistant-custom-component`
- Ruff
- Home Assistant's integration quality-scale conventions

The implementation uses a `DataUpdateCoordinator`, `ConfigEntry.runtime_data`, a UI config flow, unique entity IDs, dynamic panel discovery, diagnostics-oriented entities/attributes, and tests around the real TigoTell JSON snapshot.

Run the unit tests with:

```bash
pytest
```

Run Ruff with:

```bash
ruff check .
ruff format --check .
```

For official Home Assistant development checks, use the Home Assistant development environment and `hassfest`/`prek` as described by the Home Assistant developer documentation.

## Known limitations

- TigoTell's `/json` endpoint provides current telemetry, not accumulated daily energy. The integration therefore does not fabricate an energy sensor.
- Tigo RSSI is a Tigo protocol value, not a standardized dBm measurement. The integration intentionally exposes a qualitative signal level and preserves the raw number as an attribute.
- `last_updated` and `last_seen_ms` are TigoTell monotonic uptime values, not Unix timestamps. The Last update entity estimates wall-clock time using TigoTell's current uptime.
