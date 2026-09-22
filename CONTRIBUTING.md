# Contributing

Please follow the Home Assistant integration development guidance and run the local tests and Ruff checks before submitting changes.

The integration is intentionally split into a small `tigotell-client` PyPI package and the Home Assistant custom integration. Changes to the API/client should include unit tests using representative TigoTell `/json` snapshots.

Do not add MQTT or InfluxDB as runtime dependencies: the integration is intentionally a local HTTP polling integration.
