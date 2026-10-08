class TigoTellPanelCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("TigoTell Panel Card requires an entity");
    }

    this._config = {
      min: 0,
      max: 390,
      needle: false,
      severity: {
        green: 200,
        yellow: 100,
        red: 0,
      },
      ...config,
    };

    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  get aliases() {
    return {
      "0000000000000001": "B1",
      "0000000000000002": "B2",
      "0000000000000003": "B3",
      "0000000000000004": "B4",
      "0000000000000005": "B5",
      "0000000000000006": "B6",
      "0000000000000007": "B7",
      "0000000000000008": "B8",
      "0000000000000009": "B9",
      "000000000000000A": "B10",
      "000000000000000B": "B11",
      "000000000000000C": "B12",
      "000000000000000D": "B13",
      "000000000000000E": "B14",
      "000000000000000F": "B15",
      "0000000000000010": "B16",
      "0000000000000011": "B17",
    };
  }

  getAlias(barcode) {
    if (!barcode) {
      return "-";
    }

    const normalized = String(barcode).toUpperCase();

    return this.aliases[normalized] || normalized.slice(-4);
  }

  formatAge(seconds) {
    const age = Number(seconds);

    if (!Number.isFinite(age) || age < 0) {
      return "-";
    }

    if (age < 60) {
      return `${Math.round(age)}s`;
    }

    if (age < 3600) {
      const minutes = Math.floor(age / 60);
      const secs = Math.round(age % 60);

      return `${minutes}m ${secs}s`;
    }

    const hours = Math.floor(age / 3600);
    const minutes = Math.floor((age % 3600) / 60);

    return `${hours}h ${minutes}m`;
  }

  getColor(power) {
    const severity = this._config.severity;

    if (power >= severity.green) {
      return "var(--success-color, #4caf50)";
    }

    if (power >= severity.yellow) {
      return "var(--warning-color, #ff9800)";
    }

    return "var(--error-color, #f44336)";
  }

  getBarcode() {
    if (this._config.barcode) {
      return this._config.barcode;
    }

    const match = this._config.entity.match(
      /^sensor\.tigo_panel_([a-f0-9]+)_power$/i
    );

    return match ? match[1] : null;
  }

  render() {
    if (!this._hass || !this._config) {
      return;
    }

    const powerState = this._hass.states[this._config.entity];

    if (!powerState) {
      this.shadowRoot.innerHTML = `
        <style>
          ha-card {
            padding: 20px;
          }

          .error {
            color: var(--error-color);
          }
        </style>

        <ha-card>
          <div class="error">Entity not found</div>
        </ha-card>
      `;

      return;
    }

    const power = Number(powerState.state);
    const unit = powerState.attributes.unit_of_measurement || "W";

    let age = null;

    if (this._config.age_entity) {
      const ageState = this._hass.states[this._config.age_entity];

      if (ageState) {
        age = Number(ageState.state);
      }
    }

    const barcode = this.getBarcode();
    const alias = this._config.alias || this.getAlias(barcode);
    const min = Number(this._config.min);
    const max = Number(this._config.max);
    const percentage =
      max > min
        ? Math.max(0, Math.min(1, (power - min) / (max - min)))
        : 0;

    const cx = 100;
    const cy = 105;
    const radius = 78;
    const startX = cx - radius;
    const endX = cx + radius;
    const arcPath = `M ${startX} ${cy} A ${radius} ${radius} 0 0 1 ${endX} ${cy}`;
    const arcLength = Math.PI * radius;
    const valueLength = arcLength * percentage;
    const color = this.getColor(power);

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          height: 100%;
        }

        ha-card {
          box-sizing: border-box;
          height: 100%;
          overflow: hidden;
        }

        .card {
          box-sizing: border-box;
          width: 100%;
          height: 100%;
          padding: 10px 12px 8px;
          text-align: center;
        }

        .gauge {
          position: relative;
          width: 100%;
          height: 175px;
        }

        svg {
          display: block;
          width: 100%;
          height: 175px;
          overflow: visible;
        }

        .value {
          position: absolute;
          left: 0;
          right: 0;
          top: 91px;
          font-size: 36px;
          font-weight: 400;
          line-height: 1;
          color: var(--primary-text-color);
        }

        .details {
          margin-top: -1px;
          font-size: 14px;
          line-height: 20px;
          color: var(--primary-text-color);
          white-space: nowrap;
        }

        .alias {
          font-weight: 500;
        }

        .separator {
          padding: 0 5px;
          opacity: 0.65;
        }

        .age {
          opacity: 0.75;
        }
      </style>

      <ha-card>
        <div class="card">
          <div class="gauge">
            <svg viewBox="0 0 200 125">
              <path
                d="${arcPath}"
                fill="none"
                stroke="var(--divider-color)"
                stroke-width="30"
                stroke-linecap="butt"
                opacity="0.25"
              />
              <path
                d="${arcPath}"
                fill="none"
                stroke="${color}"
                stroke-width="30"
                stroke-linecap="butt"
                stroke-dasharray="${valueLength} ${arcLength}"
              />
            </svg>
            <div class="value">
              ${Number.isFinite(power) ? `${Math.round(power)} ${unit}` : "-"}
            </div>
          </div>
          <div class="details">
            <span class="alias">${alias}</span>
            <span class="separator">|</span>
            <span class="age">${this.formatAge(age)}</span>
          </div>
        </div>
      </ha-card>
    `;
  }

  getCardSize() {
    return 3;
  }
}

customElements.define("tigotell-panel-card", TigoTellPanelCard);