/**
 * aito-card — 问界 M8 Home Assistant Card
 * 数据源：aito 集成（华为 IVCS 官方接口）
 * Usage:  type: custom:aito-card
 *
 * 骨架只构建一次，之后只更新文本与 class，好让开关的 CSS transition 能播出来。
 */

const PREP_SWITCH = 'switch.aito_prep_car';
const SENTRY_SWITCH = 'switch.aito_sentry';
const PENDING_TIMEOUT_MS = 30000;
// 车图由集成合成到 /local/aito/car.png。带版本号 bust 浏览器强缓存——
// 集成重新合成车图后，把这个值改一下即可让所有客户端重新拉图。
const CAR_IMAGE_URL = '/local/aito/car.png?v=2';

class AitoCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._pending = {};
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) {
      this._build();
      this._built = true;
    }
    this._update();
  }

  setConfig(config) {
    this._config = config;
  }

  getCardSize() { return 6; }

  _state(id) { return this._hass?.states[id]?.state ?? '--'; }

  _build() {
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .card {
          background: var(--ha-card-background, var(--card-background-color));
          border-radius: var(--ha-card-border-radius, 12px);
          overflow: hidden;
          box-shadow: var(--ha-card-box-shadow, none);
          font-family: var(--primary-font-family, sans-serif);
          color: var(--primary-text-color);
          padding: 16px;
        }

        .hero {
          display: flex;
          align-items: center;
          gap: 14px;
          margin-bottom: 12px;
        }
        .hero-img-wrap {
          flex: 0 0 auto;
          width: 100px; height: 65px;
          display: flex; align-items: center; justify-content: center;
        }
        .hero-img-wrap img { max-width: 100%; max-height: 100%; object-fit: contain; }
        .hero-info { flex: 1; min-width: 0; }
        .hero-name {
          font-size: 0.75em; font-weight: 500;
          color: var(--secondary-text-color);
          margin-bottom: 2px;
        }
        .hero-soc-row { display: flex; align-items: baseline; gap: 3px; margin-bottom: 4px; }
        .hero-soc-num { font-size: 1.8em; font-weight: 700; line-height: 1; }
        .hero-soc-unit { font-size: 0.8em; color: var(--secondary-text-color); }
        .hero-range {
          display: flex; gap: 10px;
          font-size: 0.75em; font-weight: 500;
          color: var(--secondary-text-color);
        }
        .progress-wrap {
          width: 100%; height: 3px;
          background: var(--divider-color);
          border-radius: 2px; margin-top: 6px; overflow: hidden;
        }
        .progress-fill { height: 100%; border-radius: 2px; transition: width 0.8s ease, background 0.4s ease; }

        .ctrl-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
        .ctrl-cell {
          display: flex; align-items: center; justify-content: space-between;
          gap: 6px;
          background: var(--secondary-background-color);
          border-radius: 12px;
          padding: 8px 10px;
          min-width: 0;
        }
        .ctrl-text { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
        .ctrl-name {
          font-size: 0.75em; font-weight: 600;
          white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .ctrl-state {
          font-size: 0.6em; font-weight: 500;
          color: var(--secondary-text-color);
          white-space: nowrap;
          transition: color 0.25s;
        }
        .ctrl-state.on { color: #4ade80; }

        .switch {
          position: relative;
          flex: 0 0 auto;
          width: 42px; height: 24px;
          border: none; padding: 0;
          border-radius: 12px;
          background: var(--divider-color);
          cursor: pointer;
          transition: background 0.25s ease;
          -webkit-tap-highlight-color: transparent;
        }
        .switch .knob {
          position: absolute; top: 3px; left: 3px;
          width: 18px; height: 18px;
          border-radius: 50%;
          background: #fff;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.45);
          transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .switch.on { background: #4ade80; }
        .switch.on .knob { transform: translateX(18px); }
        .switch.pending { cursor: progress; pointer-events: none; }
        .switch.pending .knob { animation: knob-pulse 1s ease-in-out infinite; }
        .switch.unavailable { opacity: 0.4; pointer-events: none; }
        @keyframes knob-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.35; }
        }

        .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 10px; }
        .grid + .grid { margin-top: 6px; }
        .cell {
          background: var(--secondary-background-color);
          border-radius: 10px;
          padding: 8px 4px;
          display: flex; flex-direction: column;
          align-items: center; text-align: center; gap: 2px;
        }
        .cell-val { font-size: 0.82em; font-weight: 600; white-space: nowrap; }
        .cell-label { font-size: 0.62em; color: var(--secondary-text-color); }

        .footer {
          display: flex; justify-content: space-between;
          margin-top: 10px;
          font-size: 0.62em;
          color: var(--secondary-text-color);
        }
      </style>

      <div class="card">
        <div class="hero">
          <div class="hero-img-wrap">
            <img src="${CAR_IMAGE_URL}" alt="车辆"
                 onerror="this.style.visibility='hidden'" />
          </div>
          <div class="hero-info">
            <div class="hero-name" id="name"></div>
            <div class="hero-soc-row">
              <span class="hero-soc-num" id="soc"></span>
              <span class="hero-soc-unit">%</span>
            </div>
            <div class="hero-range">
              <span id="elec"></span>
              <span id="fuel"></span>
            </div>
            <div class="progress-wrap"><div class="progress-fill" id="bar"></div></div>
          </div>
        </div>

        <div class="ctrl-grid">
          <div class="ctrl-cell">
            <span class="ctrl-text">
              <span class="ctrl-name">🚗 备车</span>
              <span class="ctrl-state" id="prep-state"></span>
            </span>
            <button class="switch" id="prep-sw" role="switch" aria-label="立即备车">
              <span class="knob"></span>
            </button>
          </div>
          <div class="ctrl-cell">
            <span class="ctrl-text">
              <span class="ctrl-name">🛡️ 哨兵</span>
              <span class="ctrl-state" id="sentry-state"></span>
            </span>
            <button class="switch" id="sentry-sw" role="switch" aria-label="哨兵模式">
              <span class="knob"></span>
            </button>
          </div>
        </div>

        <div class="grid">
          <div class="cell"><div class="cell-val" id="sum-range"></div><div class="cell-label">综合续航</div></div>
          <div class="cell"><div class="cell-val" id="inside"></div><div class="cell-label">车内</div></div>
          <div class="cell"><div class="cell-val" id="ac"></div><div class="cell-label">空调</div></div>
          <div class="cell"><div class="cell-val" id="status"></div><div class="cell-label">状态</div></div>
        </div>

        <div class="grid">
          <div class="cell"><div class="cell-val" id="tire-fl"></div><div class="cell-label">左前</div></div>
          <div class="cell"><div class="cell-val" id="tire-fr"></div><div class="cell-label">右前</div></div>
          <div class="cell"><div class="cell-val" id="tire-rl"></div><div class="cell-label">左后</div></div>
          <div class="cell"><div class="cell-val" id="tire-rr"></div><div class="cell-label">右后</div></div>
        </div>

        <div class="footer">
          <span id="updated"></span>
          <span id="odo"></span>
        </div>
      </div>
    `;

    this._$ = (id) => this.shadowRoot.getElementById(id);
    this._$('prep-sw').addEventListener('click', () => this._toggle(PREP_SWITCH));
    this._$('sentry-sw').addEventListener('click', () => this._toggle(SENTRY_SWITCH));
  }

  _toggle(entity) {
    const current = this._state(entity);
    if (current !== 'on' && current !== 'off') return;
    const target = current === 'on' ? 'off' : 'on';
    this._pending[entity] = { target, since: Date.now() };
    this._update();
    this._hass?.callService('switch', target === 'on' ? 'turn_on' : 'turn_off', { entity_id: entity });
    // 车端回执可能要几秒；兜底超时，免得开关卡在下发中
    setTimeout(() => {
      if (this._pending[entity]) {
        delete this._pending[entity];
        this._update();
      }
    }, PENDING_TIMEOUT_MS);
  }

  _updateSwitch(entity, swId, stateId) {
    const sw = this._$(swId);
    const label = this._$(stateId);
    const state = this._state(entity);
    const pending = this._pending[entity];

    if (pending) {
      // 状态已经走到目标值，或等太久了，就退出 pending
      if (state === pending.target || Date.now() - pending.since > PENDING_TIMEOUT_MS) {
        delete this._pending[entity];
      }
    }
    const stillPending = Boolean(this._pending[entity]);
    const on = stillPending ? this._pending[entity].target === 'on' : state === 'on';
    const usable = state === 'on' || state === 'off';

    sw.classList.toggle('on', on);
    sw.classList.toggle('pending', stillPending);
    sw.classList.toggle('unavailable', !usable && !stillPending);
    sw.setAttribute('aria-checked', String(on));
    label.textContent = stillPending ? '下发中…' : usable ? (on ? '已开启' : '已关闭') : '不可用';
    label.classList.toggle('on', on && !stillPending);
  }

  _update() {
    if (!this._hass) return;

    const num = (v, digits = 1) =>
      Number.isFinite(parseFloat(v)) ? parseFloat(v).toFixed(digits) : '--';
    const int = (v) => (Number.isFinite(parseFloat(v)) ? String(Math.round(parseFloat(v))) : '--');

    const charge = this._state('sensor.aito_charge_state');
    const soc = this._state('sensor.aito_soc');
    const socN = parseFloat(soc) || 0;

    // 车名取接口的车型名；实体未就绪时回退
    const model = this._state('sensor.aito_model');
    const title = model && model !== '--' && model !== 'unknown' ? model : '我的车';
    this._$('name').textContent =
      `${title} · ${charge === '未充电' || charge === '--' ? charge : '⚡' + charge}`;
    this._$('soc').textContent = int(soc);
    this._$('elec').textContent = `⚡ ${int(this._state('sensor.aito_elec_range'))} km`;
    this._$('fuel').textContent = `⛽ ${int(this._state('sensor.aito_fuel_range'))} km`;

    const bar = this._$('bar');
    bar.style.width = `${socN}%`;
    bar.style.background = socN > 60 ? '#4ade80' : socN > 30 ? '#facc15' : '#f87171';

    this._updateSwitch(PREP_SWITCH, 'prep-sw', 'prep-state');
    this._updateSwitch(SENTRY_SWITCH, 'sentry-sw', 'sentry-state');

    this._$('sum-range').textContent = `🛣️ ${int(this._state('sensor.aito_sum_range'))} km`;
    this._$('inside').textContent = `🌡️ ${num(this._state('sensor.aito_inside_temp'))}°`;
    this._$('ac').textContent = `❄️ ${num(this._state('sensor.aito_ac_temp'))}°`;

    const parkingState = this._state('sensor.aito_parking');
    const parked = parkingState === '停泊';
    this._$('status').textContent =
      parkingState === '--' || parkingState === 'unknown' || parkingState === 'unavailable'
        ? '🚘 --'
        : `${parked ? '🅿️' : '🚗'} ${parkingState}`;

    for (const [id, entity] of [
      ['tire-fl', 'sensor.aito_tire_fl'],
      ['tire-fr', 'sensor.aito_tire_fr'],
      ['tire-rl', 'sensor.aito_tire_rl'],
      ['tire-rr', 'sensor.aito_tire_rr'],
    ]) {
      const v = parseFloat(this._state(entity));
      const el = this._$(id);
      if (Number.isFinite(v) && v > 0) {
        el.textContent = v.toFixed(1);
        el.style.color = v >= 2.3 ? '#4ade80' : '#f87171';
      } else {
        // 车辆休眠时接口对四个轮子都返回 -1，集成已过滤成 unknown
        el.textContent = '--';
        el.style.color = 'var(--secondary-text-color)';
      }
    }

    this._$('updated').textContent = `更新于 ${this._fmtTime(this._state('sensor.aito_updated_at'))}`;
    this._$('odo').textContent = `总里程 ${num(this._state('sensor.aito_odometer'))} km`;
  }

  _fmtTime(iso) {
    if (!iso || iso === '--' || iso === 'unknown' || iso === 'unavailable') return '--';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '--';
    const p = (n) => String(n).padStart(2, '0');
    return `${p(d.getMonth() + 1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }
}

customElements.define('aito-card', AitoCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'aito-card',
  name: '问界 M8',
  description: '问界 M8 车辆状态与控制（aito 集成）',
  preview: false,
});
