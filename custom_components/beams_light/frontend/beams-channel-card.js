class BeamsChannelCard extends HTMLElement {
  setConfig(config) {
    if (!Array.isArray(config.entities) || config.entities.length === 0) {
      throw new Error("Set one or more number entities in 'entities'");
    }
    this.config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return (this.config?.entities?.length || 1) + 1;
  }

  _render() {
    if (!this._hass || !this.config) {
      return;
    }

    // Home Assistant publishes state updates independently of a drag operation.
    // Recreating a native range input while it is being dragged makes its thumb
    // visibly jump back to the last reported controller value.
    if (this._isDragging) {
      return;
    }

    const rows = this.config.entities
      .map((entityId) => this._hass.states[entityId])
      .filter(Boolean)
      .map((state) => {
        const hasReportedValue = state.state !== "unavailable" && state.state !== "unknown";
        const reportedValue = hasReportedValue
          ? Number(state.state)
          : Number(state.attributes.current_value);
        const unavailable = !Number.isFinite(reportedValue);
        const editable = !state.attributes.service_mode && hasReportedValue;
        const pendingValue = this._pendingValues?.get(state.entity_id);
        if (pendingValue && Math.abs(reportedValue - pendingValue) < 0.011) {
          this._pendingValues.delete(state.entity_id);
        }
        const value = pendingValue ?? (unavailable ? 0 : reportedValue);
        const color = state.attributes.color || "var(--primary-color)";
        const name = state.attributes.friendly_name || state.entity_id;
        return `
          <div class="channel ${unavailable ? "unavailable" : ""}">
            <div class="label"><span class="dot" style="background:${color}"></span>${name}</div>
            <div class="control">
              <input type="range" min="0" max="100" step="0.01" value="${value}" ${editable ? "" : "disabled"}
                data-entity-id="${state.entity_id}" style="--channel-color:${color}">
              <span>${unavailable ? "—" : `${value.toFixed(2)}%`}</span>
            </div>
          </div>`;
      })
      .join("");

    this.innerHTML = `
      <ha-card>
        <div class="header">${this.config.title || "BEAMS Channels"}</div>
        <div class="channels">${rows}</div>
      </ha-card>
      <style>
        :host { display: block; }
        .header { font-size: 20px; font-weight: 500; padding: 16px 16px 8px; }
        .channels { padding: 0 16px 12px; }
        .channel { padding: 10px 0; border-bottom: 1px solid var(--divider-color); }
        .channel:last-child { border-bottom: 0; }
        .label { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
        .dot { width: 12px; height: 12px; border-radius: 50%; box-shadow: 0 0 4px currentColor; }
        .control { display: grid; grid-template-columns: 1fr 52px; align-items: center; gap: 12px; }
        input[type=range] { width: 100%; accent-color: var(--channel-color); }
        .control span { text-align: right; font-variant-numeric: tabular-nums; }
        .unavailable { opacity: 0.55; }
      </style>`;

    this.querySelectorAll("input[type=range]").forEach((slider) => {
      slider.addEventListener("pointerdown", (event) => {
        this._isDragging = true;
        this._pendingValues = this._pendingValues || new Map();
        this._pendingValues.set(
          event.target.dataset.entityId,
          Number(event.target.value),
        );
      });
      slider.addEventListener("input", (event) => {
        this._isDragging = true;
        this._pendingValues = this._pendingValues || new Map();
        this._pendingValues.set(
          event.target.dataset.entityId,
          Number(event.target.value),
        );
        const output = event.target.parentElement.querySelector("span");
        output.textContent = `${Number(event.target.value).toFixed(2)}%`;
      });
      slider.addEventListener("change", (event) => {
        const value = Number(event.target.value);
        this._isDragging = false;
        this._pendingValues = this._pendingValues || new Map();
        this._pendingValues.set(event.target.dataset.entityId, value);
        this._render();
        setTimeout(() => {
          if (this._pendingValues?.get(event.target.dataset.entityId) === value) {
            this._pendingValues.delete(event.target.dataset.entityId);
            this._render();
          }
        }, 5000);
        this._hass.callService("number", "set_value", {
          entity_id: event.target.dataset.entityId,
          value,
        });
      });
    });
  }
}

if (!customElements.get("beams-channel-card")) {
  customElements.define("beams-channel-card", BeamsChannelCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "beams-channel-card")) {
  window.customCards.push({
    type: "beams-channel-card",
    name: "BEAMS Channels",
    description: "Color-coded BEAMS channel sliders",
  });
}

class BeamsSpectrumCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error("Set the source light entity in 'entity'");
    }
    this.config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  _render() {
    const state = this._hass?.states[this.config?.entity];
    const points = state?.attributes?.spectrum_points;
    if (!Array.isArray(points) || points.length === 0) {
      this.innerHTML = `<ha-card><div class="spectrum-header">${this.config?.title || "Current spectrum"}</div><div class="spectrum-empty">Spectrum data unavailable</div></ha-card>`;
      return;
    }

    const left = 42;
    const top = 14;
    const width = 558;
    const height = 196;
    const minWavelength = 360;
    const maxWavelength = 800;
    const maxValue = Math.max(...points.map(([, value]) => Number(value) || 0), 0.001);
    const x = (wavelength) => left + ((Number(wavelength) - minWavelength) / (maxWavelength - minWavelength)) * width;
    const y = (value) => top + height - ((Number(value) || 0) / maxValue) * height;
    const line = points.map(([wavelength, value]) => `${x(wavelength).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
    const area = `${left},${top + height} ${line} ${left + width},${top + height}`;
    const xTicks = [360, 450, 540, 620, 710, 800];
    const yTicks = [0, 0.25, 0.5, 0.75, 1];
    const grid = [
      ...xTicks.map((tick) => `<line x1="${x(tick)}" y1="${top}" x2="${x(tick)}" y2="${top + height}"/>`),
      ...yTicks.map((tick) => `<line x1="${left}" y1="${y(tick * maxValue)}" x2="${left + width}" y2="${y(tick * maxValue)}"/>`),
    ].join("");
    const labels = `${xTicks.map((tick) => `<text x="${x(tick)}" y="${top + height + 20}" text-anchor="middle">${tick}</text>`).join("")}${yTicks.map((tick) => `<text x="${left - 7}" y="${y(tick * maxValue) + 4}" text-anchor="end">${(tick * maxValue).toFixed(2).replace(/0+$/, "").replace(/\\.$/, "")}</text>`).join("")}`;
    this.innerHTML = `
      <ha-card>
        <div class="spectrum-header">${this.config.title || "Current spectrum"}</div>
        <svg viewBox="0 0 620 246" role="img" aria-label="Current light spectrum">
          <defs><linearGradient id="beams-spectrum-gradient" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stop-color="#4b00a8"/><stop offset="20%" stop-color="#0044ff"/><stop offset="36%" stop-color="#00ffff"/><stop offset="48%" stop-color="#00ff00"/><stop offset="60%" stop-color="#ffff00"/><stop offset="75%" stop-color="#ff5500"/><stop offset="100%" stop-color="#dd0000"/>
          </linearGradient></defs>
          <g class="grid">${grid}</g>
          <polygon points="${area}" fill="url(#beams-spectrum-gradient)" opacity="0.9"/>
          <polyline points="${line}" fill="none" stroke="rgba(255,255,255,0.35)" stroke-width="1"/>
          <g class="labels">${labels}<text x="4" y="12">PPFD/nm</text><text x="${left + width}" y="${top + height + 20}" text-anchor="end">nm</text></g>
        </svg>
      </ha-card>
      <style>
        :host { display: block; }
        .spectrum-header { font-size: 20px; font-weight: 500; padding: 16px 16px 4px; }
        .spectrum-empty { padding: 12px 16px 20px; color: var(--secondary-text-color); }
        svg { width: 100%; display: block; padding: 0 8px 8px; box-sizing: border-box; }
        .grid { stroke: var(--divider-color); stroke-width: 1; }
        .labels { fill: var(--secondary-text-color); font: 12px serif; }
      </style>`;
  }
}

if (!customElements.get("beams-spectrum-card")) {
  customElements.define("beams-spectrum-card", BeamsSpectrumCard);
}
if (!window.customCards.some((card) => card.type === "beams-spectrum-card")) {
  window.customCards.push({
    type: "beams-spectrum-card",
    name: "BEAMS Spectrum",
    description: "Current BEAMS spectral distribution",
  });
}
