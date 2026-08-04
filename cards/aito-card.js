/**
 * aito-card — 问界 M8 Home Assistant Card
 * 数据源：aito 集成（华为 IVCS 官方接口）
 * Usage:  type: custom:aito-card
 *
 * 骨架只构建一次，之后只更新文本与 class，好让开关的 CSS transition 能播出来。
 */

// 用集成实体的 translation_key 定位实体（稳定，不随 entity_id 命名变化）
const PREP_KEY = 'now_departure_plan';
const SENTRY_KEY = 'sentry_mode';
const CLIMATE_KEY = 'air_conditioner';
const MOVE_STATUS_KEY = 'vehicle_move_status';
const PENDING_TIMEOUT_MS = 30000;
// 第一个控制键：有备车能力(M8)就是备车开关，没有(M5)就退化为空调开关。
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

  // 按集成 platform + translation_key 反查 entity_id（不依赖实体命名），带缓存
  _eid(tk) {
    const ents = this._hass?.entities;
    if (!ents) return null;
    if (ents !== this._entsRef) {
      this._entsRef = ents;
      this._map = {};
      for (const id in ents) {
        const e = ents[id];
        if (e.platform === 'aito' && e.translation_key) this._map[e.translation_key] = id;
      }
    }
    return this._map[tk] || null;
  }

  // 取某 translation_key 对应实体的 state
  _s(tk) { return this._state(this._eid(tk)); }

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
          cursor: pointer;
          transition: transform 0.1s, background 0.15s;
          -webkit-tap-highlight-color: transparent;
        }
        .cell:hover { background: var(--divider-color); }
        .cell:active { transform: scale(0.95); }
        .footer span[data-entity] { cursor: pointer; }
        .footer span[data-entity]:hover { color: var(--primary-text-color); }
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
              <span class="ctrl-name" id="prep-name">🚗 备车</span>
              <span class="ctrl-state" id="prep-state"></span>
            </span>
            <button class="switch" id="prep-sw" role="switch" aria-label="立即备车/空调">
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
          <div class="cell" data-entity="sum_remaining_mileage"><div class="cell-val" id="sum-range"></div><div class="cell-label">综合续航</div></div>
          <div class="cell" data-entity="inside_temperature"><div class="cell-val" id="inside"></div><div class="cell-label">车内</div></div>
          <div class="cell" data-entity="air_conditioner"><div class="cell-val" id="ac"></div><div class="cell-label">空调</div></div>
          <div class="cell" data-entity="vehicle_move_status"><div class="cell-val" id="status"></div><div class="cell-label">状态</div></div>
        </div>

        <div class="grid">
          <div class="cell" data-entity="tire_pressure_left_front"><div class="cell-val" id="tire-fl"></div><div class="cell-label">左前</div></div>
          <div class="cell" data-entity="tire_pressure_right_front"><div class="cell-val" id="tire-fr"></div><div class="cell-label">右前</div></div>
          <div class="cell" data-entity="tire_pressure_left_back"><div class="cell-val" id="tire-rl"></div><div class="cell-label">左后</div></div>
          <div class="cell" data-entity="tire_pressure_right_back"><div class="cell-val" id="tire-rr"></div><div class="cell-label">右后</div></div>
        </div>

        <div class="footer">
          <span data-entity="last_updated_at" id="updated"></span>
          <span data-entity="total_mileage" id="odo"></span>
        </div>
      </div>
    `;

    this._$ = (id) => this.shadowRoot.getElementById(id);
    this._$('prep-sw').addEventListener('click', () => this._togglePrimary());
    this._$('sentry-sw').addEventListener('click', () => this._toggle(this._eid(SENTRY_KEY)));
    // 每个状态格点击打开对应实体的详情弹窗（data-entity 存 translation_key，运行时反查）
    this.shadowRoot.querySelectorAll('[data-entity]').forEach((el) => {
      el.addEventListener('click', () => this._moreInfo(this._eid(el.dataset.entity)));
    });
  }

  // 派发 HA 标准的 more-info 事件，打开实体详情（数值型带历史图表，climate 是控制界面）
  _moreInfo(entityId) {
    if (!entityId || !this._hass?.states[entityId]) return;
    this.dispatchEvent(
      new CustomEvent('hass-more-info', { detail: { entityId }, bubbles: true, composed: true }),
    );
  }

  // 定位本车的 aito 空调 climate 实体：优先注册表反查，回退按 rapid_cool preset 扫描
  _climateId() {
    const byReg = this._eid(CLIMATE_KEY);
    if (byReg) return byReg;
    const s = this._hass?.states || {};
    return Object.keys(s).find(
      (id) =>
        id.startsWith('climate.') &&
        Array.isArray(s[id].attributes?.preset_modes) &&
        s[id].attributes.preset_modes.includes('rapid_cool'),
    );
  }

  // 第一个控制键的当前配置：优先备车，其次空调
  _primary() {
    const prep = this._eid(PREP_KEY);
    if (prep && this._hass?.states[prep]) {
      return { entity: prep, domain: 'switch', name: '🚗 备车' };
    }
    const climate = this._climateId();
    if (climate) {
      return { entity: climate, domain: 'climate', name: '❄️ 空调' };
    }
    return null;
  }

  _isOn(p) {
    const state = this._state(p.entity);
    return p.domain === 'climate' ? state !== 'off' && this._known(p, state) : state === 'on';
  }

  _known(p, state) {
    return p.domain === 'climate'
      ? state !== '--' && state !== 'unavailable' && state !== 'unknown'
      : state === 'on' || state === 'off';
  }

  _togglePrimary() {
    const p = this._primary();
    if (!p || !this._known(p, this._state(p.entity))) return;
    const target = this._isOn(p) ? 'off' : 'on';
    this._pending[p.entity] = { target, since: Date.now() };
    this._update();
    this._hass?.callService(p.domain, target === 'on' ? 'turn_on' : 'turn_off', { entity_id: p.entity });
    setTimeout(() => {
      if (this._pending[p.entity]) {
        delete this._pending[p.entity];
        this._update();
      }
    }, PENDING_TIMEOUT_MS);
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

  // 第一个控制键的状态渲染（备车走 switch 语义，空调走 climate 开/关语义）
  _updatePrimary() {
    const p = this._primary();
    const sw = this._$('prep-sw');
    const nameEl = this._$('prep-name');
    const label = this._$('prep-state');
    if (!p) {
      nameEl.textContent = '🚗 备车';
      sw.classList.remove('on', 'pending');
      sw.classList.add('unavailable');
      label.textContent = '不可用';
      label.classList.remove('on');
      return;
    }
    nameEl.textContent = p.name;
    const state = this._state(p.entity);
    const pending = this._pending[p.entity];
    if (pending && (this._isOn(p) === (pending.target === 'on') || Date.now() - pending.since > PENDING_TIMEOUT_MS)) {
      delete this._pending[p.entity];
    }
    const stillPending = Boolean(this._pending[p.entity]);
    const on = stillPending ? this._pending[p.entity].target === 'on' : this._isOn(p);
    const usable = this._known(p, state);
    sw.classList.toggle('on', on);
    sw.classList.toggle('pending', stillPending);
    sw.classList.toggle('unavailable', !usable && !stillPending);
    sw.setAttribute('aria-checked', String(on));
    label.textContent = stillPending ? '下发中…' : usable ? (on ? '已开启' : '已关闭') : '不可用';
    label.classList.toggle('on', on && !stillPending);
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

    const charge = this._s('charge_status');
    const soc = this._s('battery_soc');
    const socN = parseFloat(soc) || 0;

    // 车名取接口的车型名；实体未就绪时回退
    const model = this._s('model');
    const title = model && model !== '--' && model !== 'unknown' ? model : '我的车';
    this._$('name').textContent =
      `${title} · ${charge === '未充电' || charge === '--' ? charge : '⚡' + charge}`;
    this._$('soc').textContent = int(soc);
    this._$('elec').textContent = `⚡ ${int(this._s('electric_wltc_remaining_mileage'))} km`;
    this._$('fuel').textContent = `⛽ ${int(this._s('fuel_wltc_remaining_mileage'))} km`;

    const bar = this._$('bar');
    bar.style.width = `${socN}%`;
    bar.style.background = socN > 60 ? '#4ade80' : socN > 30 ? '#facc15' : '#f87171';

    this._updatePrimary();
    this._updateSwitch(this._eid(SENTRY_KEY), 'sentry-sw', 'sentry-state');

    this._$('sum-range').textContent = `🛣️ ${int(this._s('sum_remaining_mileage'))} km`;
    this._$('inside').textContent = `🌡️ ${num(this._s('inside_temperature'))}°`;
    this._$('ac').textContent = `❄️ ${num(this._s('air_conditioner_target_temperature'))}°`;

    const moveStatus = this._s(MOVE_STATUS_KEY);
    const moveStatusTranslationKey = `component.aito.entity.sensor.${MOVE_STATUS_KEY}.state.${moveStatus}`;
    const localizedMoveStatus = this._hass?.localize?.(moveStatusTranslationKey);
    const displayMoveStatus =
      localizedMoveStatus === moveStatusTranslationKey ? moveStatus : localizedMoveStatus || moveStatus;
    this._$('status').textContent =
      moveStatus === '--' || moveStatus === 'unknown' || moveStatus === 'unavailable'
        ? '🚘 --'
        : `${moveStatus === '0' ? '🅿️' : '🚗'} ${displayMoveStatus}`;

    for (const [id, tk] of [
      ['tire-fl', 'tire_pressure_left_front'],
      ['tire-fr', 'tire_pressure_right_front'],
      ['tire-rl', 'tire_pressure_left_back'],
      ['tire-rr', 'tire_pressure_right_back'],
    ]) {
      const v = parseFloat(this._s(tk));
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

    this._$('updated').textContent = `更新于 ${this._fmtTime(this._s('last_updated_at'))}`;
    this._$('odo').textContent = `总里程 ${num(this._s('total_mileage'))} km`;
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
