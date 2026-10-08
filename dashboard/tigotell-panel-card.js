class TigoTellPanelCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
  }

  setConfig(config) {
    this._config = {
      title: "Solar panels",
      min: 0,
      max: 390,
      ...config,
      severity: {
        green: 200,
        yellow: 100,
        red: 0,
        ...(config.severity || {}),
      },
      aliases: { ...(config.aliases || {}) },
      panel_order: [...(config.panel_order || [])],
    };
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  static getConfigElement() {
    return document.createElement("tigotell-panel-card-editor");
  }

  static getStubConfig() {
    return { type: "custom:tigotell-panel-card" };
  }

  getCardSize() {
    return Math.max(3, Math.ceil(discoverPanels(this._hass).length / 3) * 3);
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
      return `${Math.floor(age / 60)}m ${Math.round(age % 60)}s`;
    }

    return `${Math.floor(age / 3600)}h ${Math.floor((age % 3600) / 60)}m`;
  }

  getColor(power) {
    if (power >= this._config.severity.green) {
      return "var(--success-color, #4caf50)";
    }

    if (power >= this._config.severity.yellow) {
      return "var(--warning-color, #ff9800)";
    }

    return "var(--error-color, #f44336)";
  }

  render() {
    if (!this._hass || !this._config) {
      return;
    }

    const panels = discoverPanels(this._hass, this._config.panel_order);

    if (panels.length === 0) {
      this.shadowRoot.innerHTML = `
        <style>
          ha-card {
            padding: 20px;
            color: var(--secondary-text-color);
          }
        </style>
        <ha-card>No TigoTell panels found</ha-card>
      `;
      return;
    }

    const min = Number(this._config.min);
    const max = Number(this._config.max);
    const cards = panels
      .map((panel, index) => {
        const power = Number(panel.powerState.state);
        const unit = panel.powerState.attributes.unit_of_measurement || "W";
        const alias = this._config.aliases[panel.barcode] || `Panel ${index + 1}`;
        const percentage =
          max > min
            ? Math.max(0, Math.min(1, (power - min) / (max - min)))
            : 0;
        const radius = 78;
        const arcLength = Math.PI * radius;
        const arcPath = `M 22 105 A ${radius} ${radius} 0 0 1 178 105`;
        const age = panel.ageState ? panel.ageState.state : null;

        return `
          <article class="panel">
            <div class="gauge">
              <svg viewBox="0 0 200 125" aria-hidden="true">
                <path d="${arcPath}" fill="none" stroke="var(--divider-color)" stroke-width="30" opacity="0.25" />
                <path d="${arcPath}" fill="none" stroke="${this.getColor(power)}" stroke-width="30" stroke-dasharray="${arcLength * percentage} ${arcLength}" />
              </svg>
              <div class="value">
                ${Number.isFinite(power) ? `${Math.round(power)} ${escapeHtml(unit)}` : "-"}
              </div>
            </div>
            <div class="details">
              <span class="alias">${escapeHtml(alias)}</span>
              <span class="separator">|</span>
              <span class="age">${this.formatAge(age)}</span>
            </div>
          </article>
        `;
      })
      .join("");

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }

        ha-card {
          box-sizing: border-box;
          overflow: hidden;
        }

        header {
          padding: 16px 16px 0;
          font-size: 16px;
          font-weight: 500;
        }

        .panels {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
          gap: 8px;
          padding: 8px;
        }

        .panel {
          min-width: 0;
          padding: 8px 6px;
          text-align: center;
        }

        .gauge {
          position: relative;
          height: 145px;
        }

        svg {
          display: block;
          width: 100%;
          height: 145px;
          overflow: visible;
        }

        .value {
          position: absolute;
          top: 75px;
          right: 0;
          left: 0;
          font-size: 30px;
          line-height: 1;
          color: var(--primary-text-color);
        }

        .details {
          overflow: hidden;
          font-size: 14px;
          line-height: 20px;
          color: var(--primary-text-color);
          white-space: nowrap;
          text-overflow: ellipsis;
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
        <header>${escapeHtml(this._config.title)}</header>
        <div class="panels">${cards}</div>
      </ha-card>
    `;
  }
}

function discoverPanels(hass, preferredOrder = []) {
  const states = Object.entries(hass?.states || {});
  const ageByBarcode = new Map();

  for (const [, state] of states) {
    const barcode = state.attributes?.barcode;

    if (barcode && state.attributes.unit_of_measurement === "s") {
      ageByBarcode.set(String(barcode).toUpperCase(), state);
    }
  }

  return states
    .filter(
      ([entityId, state]) =>
        entityId.startsWith("sensor.") &&
        state.attributes?.device_class === "power" &&
        state.attributes?.barcode
    )
    .map(([entityId, powerState]) => {
      const barcode = String(powerState.attributes.barcode).toUpperCase();

      return {
        barcode,
        entityId,
        powerState,
        ageState: ageByBarcode.get(barcode),
      };
    })
    .sort((left, right) => {
      const leftPosition = preferredOrder.indexOf(left.barcode);
      const rightPosition = preferredOrder.indexOf(right.barcode);

      if (leftPosition === -1 && rightPosition !== -1) {
        return 1;
      }

      if (rightPosition === -1 && leftPosition !== -1) {
        return -1;
      }

      if (leftPosition !== rightPosition) {
        return leftPosition - rightPosition;
      }

      return left.barcode.localeCompare(right.barcode);
    });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };

    return entities[character];
  });
}

class TigoTellPanelCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = { aliases: {}, panel_order: [] };
    this._panelSignature = null;
  }

  setConfig(config) {
    this._config = {
      ...config,
      aliases: { ...(config.aliases || {}) },
      panel_order: [...(config.panel_order || [])],
    };
    this._panelSignature = this._hass
      ? discoverPanels(this._hass, this._config.panel_order)
          .map((panel) => panel.barcode)
          .join(",")
      : null;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    const panelSignature = discoverPanels(hass, this._config.panel_order)
      .map((panel) => panel.barcode)
      .join(",");

    if (panelSignature !== this._panelSignature) {
      this._panelSignature = panelSignature;
      this.render();
    }
  }

  render() {
    if (!this._hass) {
      return;
    }

    const panels = discoverPanels(this._hass, this._config.panel_order);
    const rows = panels
      .map((panel, index) => {
        const alias = this._config.aliases[panel.barcode] || "";

        return `
          <div class="row">
            <span class="barcode">${escapeHtml(panel.barcode)}</span>
            <input
              type="text"
              data-barcode="${escapeHtml(panel.barcode)}"
              value="${escapeHtml(alias)}"
              placeholder="Panel ${index + 1}"
              aria-label="Alias for panel ${escapeHtml(panel.barcode)}"
            />
            <div class="move-controls">
              <button
                type="button"
                data-move="-1"
                data-barcode="${escapeHtml(panel.barcode)}"
                aria-label="Move panel ${escapeHtml(panel.barcode)} up"
                title="Move up"
                ${index === 0 ? "disabled" : ""}
              >&#8593;</button>
              <button
                type="button"
                data-move="1"
                data-barcode="${escapeHtml(panel.barcode)}"
                aria-label="Move panel ${escapeHtml(panel.barcode)} down"
                title="Move down"
                ${index === panels.length - 1 ? "disabled" : ""}
              >&#8595;</button>
            </div>
          </div>
        `;
      })
      .join("");

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          color: var(--primary-text-color);
        }

        p {
          color: var(--secondary-text-color);
        }

        .row {
          display: grid;
          grid-template-columns: minmax(120px, 1fr) minmax(140px, 2fr) auto;
          gap: 12px;
          align-items: center;
          padding: 8px 0;
          border-bottom: 1px solid var(--divider-color);
        }

        .barcode {
          overflow-wrap: anywhere;
          font-family: var(--code-font-family, monospace);
          font-size: 13px;
        }

        input {
          box-sizing: border-box;
          width: 100%;
          min-height: 40px;
          padding: 8px 10px;
          border: 1px solid var(--outline-color, var(--divider-color));
          border-radius: 4px;
          background: var(--input-fill-color, var(--card-background-color));
          color: var(--primary-text-color);
          font: inherit;
        }

        input:focus {
          outline: 2px solid var(--primary-color);
          outline-offset: 1px;
        }

        .move-controls {
          display: flex;
          gap: 4px;
        }

        button {
          width: 36px;
          height: 36px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          font: inherit;
          cursor: pointer;
        }

        button:disabled {
          opacity: 0.4;
          cursor: default;
        }

        @media (max-width: 480px) {
          .row {
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 4px;
          }

          .barcode {
            grid-column: 1 / -1;
          }
        }
      </style>
      <div>
        <p>Set an alias for each discovered TigoTell panel.</p>
        ${rows || "<p>No TigoTell panels found.</p>"}
      </div>
    `;

    this.shadowRoot.querySelectorAll("input[data-barcode]").forEach((input) => {
      input.addEventListener("change", () => {
        const aliases = { ...this._config.aliases };
        const barcode = input.dataset.barcode;
        const alias = input.value.trim();

        if (alias) {
          aliases[barcode] = alias;
        } else {
          delete aliases[barcode];
        }

        this._config = { ...this._config, aliases };
        this.dispatchConfigChanged();
      });
    });

    this.shadowRoot.querySelectorAll("button[data-move]").forEach((button) => {
      button.addEventListener("click", () => {
        const panels = discoverPanels(this._hass, this._config.panel_order);
        const panelOrder = panels.map((panel) => panel.barcode);
        const currentIndex = panelOrder.indexOf(button.dataset.barcode);
        const nextIndex = currentIndex + Number(button.dataset.move);

        if (currentIndex < 0 || nextIndex < 0 || nextIndex >= panelOrder.length) {
          return;
        }

        [panelOrder[currentIndex], panelOrder[nextIndex]] = [
          panelOrder[nextIndex],
          panelOrder[currentIndex],
        ];
        this._config = { ...this._config, panel_order: panelOrder };
        this._panelSignature = panelOrder.join(",");
        this.render();
        this.dispatchConfigChanged();
      });
    });
  }

  dispatchConfigChanged() {
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      })
    );
  }
}

customElements.define("tigotell-panel-card-editor", TigoTellPanelCardEditor);
customElements.define("tigotell-panel-card", TigoTellPanelCard);