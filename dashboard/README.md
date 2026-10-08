# TigoTell Panel Card

A Lovelace card for displaying TigoTell panel power and data age. It discovers panels automatically, supports aliases and custom ordering in its visual editor, and includes newly discovered panels automatically.

The card requires the [TigoTell Home Assistant integration](https://github.com/miketkf/ha-tigotell).

## Publish through HACS

This folder is staged to become the root of a separate public GitHub repository named `lovelace-tigotell-panel-card`:

1. Copy the contents of this folder to the root of that repository.
2. Publish a GitHub release for each card version.
3. Add the repository to HACS as a **Dashboard** repository and install **TigoTell Panel Card**.
4. Add the card to a dashboard and assign aliases/order in its visual editor.

HACS installs the card, not the dashboard configuration. Import or paste [`examples/dashboard-tigotell-overview.yaml`](examples/dashboard-tigotell-overview.yaml) into a dashboard's raw configuration editor.

## Manual installation

Copy `tigotell-panel-card.js` to Home Assistant's `www` directory, register `/local/tigotell-panel-card.js` as a JavaScript module resource, and add a card:

```yaml
type: custom:tigotell-panel-card
min: 0
max: 390
severity:
  green: 200
  yellow: 100
  red: 0
```
