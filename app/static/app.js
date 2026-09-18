/**
 * GridWise 2.0 · Smart Campus Energy Optimizer
 * Frontend Application Logic & Responsive Dashboard Controller
 */

let currentScenario = null;
let publicCases = [];
let lastPlan = null;
let lastHoursInput = null;
let lastData = null;
let hoveredHour = null;

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  checkApiHealth();
  await loadPublicCases();
  if (publicCases.length > 0) {
    selectPreset(0);
  }
});

/**
 * Setup Global Event Listeners
 */
function setupEventListeners() {
  document.getElementById('btnAddNote').addEventListener('click', addNote);
  document.getElementById('btnRunOptimization').addEventListener('click', runOptimization);

  // JSON inspector copy buttons
  document.querySelectorAll('.copy-btn[data-copy-target]').forEach((btn) => {
    btn.addEventListener('click', () => copyJson(btn.dataset.copyTarget));
  });

  // Payload download buttons
  const btnDownReq = document.getElementById('btnDownloadReq');
  if (btnDownReq) {
    btnDownReq.addEventListener('click', () => {
      const scenarioId = (currentScenario && currentScenario.scenario_id) || 'scenario';
      downloadJson('requestJson', `request_${scenarioId}.json`);
    });
  }

  const btnDownRes = document.getElementById('btnDownloadRes');
  if (btnDownRes) {
    btnDownRes.addEventListener('click', () => {
      const scenarioId = (currentScenario && currentScenario.scenario_id) || 'scenario';
      downloadJson('responseJson', `schedule_${scenarioId}.json`);
    });
  }

  // CSV Export button
  const btnCsv = document.getElementById('btnExportCsv');
  if (btnCsv) {
    btnCsv.addEventListener('click', exportCsv);
  }

  // Responsive chart auto-resize on window resize
  let resizeTimeout;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      if (lastPlan && lastHoursInput) {
        renderChart(lastPlan, lastHoursInput, hoveredHour);
      }
    }, 120);
  });

  // Chart mouse & touch interactivity
  const canvas = document.getElementById('dispatchChart');
  if (canvas) {
    canvas.addEventListener('mousemove', handleChartMove);
    canvas.addEventListener('mouseleave', handleChartLeave);
    canvas.addEventListener('touchstart', handleChartTouch, { passive: true });
    canvas.addEventListener('touchmove', handleChartTouch, { passive: true });
    canvas.addEventListener('touchend', handleChartLeave);
  }
}

/**
 * Check API Health Status
 */
async function checkApiHealth() {
  const statusEl = document.getElementById('navApiStatus');
  const textEl = document.getElementById('navApiText');
  if (!statusEl || !textEl) return;

  const t0 = performance.now();
  try {
    const res = await fetch('/health');
    const ping = Math.round(performance.now() - t0);
    if (res.ok) {
      statusEl.className = 'status-pill status-live';
      textEl.innerText = `API Live · ${ping}ms`;
    } else {
      statusEl.className = 'status-pill';
      statusEl.style.background = 'rgba(239, 68, 68, 0.15)';
      statusEl.style.color = '#f87171';
      textEl.innerText = `HTTP ${res.status}`;
    }
  } catch (e) {
    statusEl.className = 'status-pill';
    statusEl.style.background = 'rgba(239, 68, 68, 0.15)';
    statusEl.style.color = '#f87171';
    textEl.innerText = 'API Offline';
  }
}

/**
 * Toast Notification System
 */
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  const icon = type === 'success' ? '✅' : (type === 'error' ? '❌' : 'ℹ️');
  toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
  
  container.appendChild(toast);

  // Auto remove after 3.2s
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 250);
  }, 3200);
}

/**
 * Load Public Scenarios from API
 */
async function loadPublicCases() {
  try {
    const res = await fetch('/api/scenarios');
    if (res.ok) {
      const data = await res.json();
      publicCases = data.cases || [];
    }
  } catch (err) {
    console.warn('Failed to load scenarios from API, using empty preset list', err);
    showToast('Could not load preset scenarios from server.', 'error');
  }

  // Update badge
  const badge = document.getElementById('presetCountBadge');
  if (badge) {
    badge.innerText = `${publicCases.length} Scenarios`;
  }

  // Render Preset Buttons
  const presetContainer = document.getElementById('presetContainer');
  presetContainer.innerHTML = '';
  publicCases.forEach((c, idx) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `preset-chip ${idx === 0 ? 'active' : ''}`;
    btn.innerText = c.id || `CASE-${idx + 1}`;
    btn.title = c.label || `Scenario ${idx + 1}`;
    btn.setAttribute('aria-label', `Select ${c.id || `CASE-${idx + 1}`}`);
    btn.onclick = () => selectPreset(idx);
    presetContainer.appendChild(btn);
  });
}

/**
 * Select Scenario Preset
 */
function selectPreset(index) {
  if (!publicCases[index]) return;
  const c = publicCases[index];
  currentScenario = JSON.parse(JSON.stringify(c.input));

  // Update active chip styling
  document.querySelectorAll('.preset-chip').forEach((el, i) => {
    el.classList.toggle('active', i === index);
  });

  populateForm(currentScenario);
  updateScenarioProfile(currentScenario);
  runOptimization();
}

/**
 * Update Scenario Energy Profile Metrics
 */
function updateScenarioProfile(scenario) {
  if (!scenario || !scenario.hours) return;
  const hours = scenario.hours;
  const totalDemand = hours.reduce((acc, h) => acc + h.demand_kwh, 0);
  const totalSolar = hours.reduce((acc, h) => acc + h.solar_kwh, 0);
  const maxTariff = Math.max(...hours.map((h) => h.tariff_bdt_per_kwh));
  const covPct = totalDemand > 0 ? ((totalSolar / totalDemand) * 100).toFixed(0) : 0;

  const elDemand = document.getElementById('profileDemand');
  const elSolar = document.getElementById('profileSolar');
  const elTariff = document.getElementById('profileTariff');
  const elCov = document.getElementById('profileSolarCoverage');

  if (elDemand) elDemand.innerText = `${Math.round(totalDemand).toLocaleString()} kWh`;
  if (elSolar) elSolar.innerText = `${Math.round(totalSolar).toLocaleString()} kWh`;
  if (elTariff) elTariff.innerText = `৳${maxTariff.toFixed(1)}/kWh`;
  if (elCov) elCov.innerText = `${covPct}%`;
}

/**
 * Populate Form Fields from Scenario Object
 */
function populateForm(scenario) {
  document.getElementById('scenarioIdInput').value = scenario.scenario_id || 'DEMO-01';
  document.getElementById('batteryCapacity').value = scenario.battery.capacity_kwh;
  document.getElementById('batteryInitial').value = scenario.battery.initial_energy_kwh;
  document.getElementById('batteryMin').value = scenario.battery.minimum_energy_kwh;
  document.getElementById('batteryMaxCharge').value = scenario.battery.max_charge_kwh_per_hour;
  document.getElementById('batteryMaxDischarge').value = scenario.battery.max_discharge_kwh_per_hour;

  renderNotesList(scenario.operator_notes || []);
}

/**
 * Render Operator Notes List
 */
function renderNotesList(notes) {
  const container = document.getElementById('notesContainer');
  container.innerHTML = '';

  const badge = document.getElementById('noteCountBadge');
  if (badge) {
    badge.innerText = `${notes.length}/3 Directives`;
  }

  notes.forEach((note, idx) => {
    const div = document.createElement('div');
    div.className = 'note-item';
    const removeBtn = notes.length > 1
      ? `<button type="button" class="btn-remove-note" data-remove-note="${idx}" aria-label="Remove note ${idx}">&times; Remove</button>`
      : '';
    div.innerHTML = `
      <div class="note-header">
        <span class="note-index-badge">Operator Note [${idx}]</span>
        ${removeBtn}
      </div>
      <textarea class="form-textarea note-text" rows="2" data-note-index="${idx}" aria-label="Operator note ${idx}">${escapeHtml(note)}</textarea>
    `;
    container.appendChild(div);
  });

  // Delegate input listeners
  container.querySelectorAll('textarea.note-text').forEach((ta) => {
    ta.addEventListener('input', (e) => {
      const i = parseInt(e.target.dataset.noteIndex, 10);
      if (!isNaN(i)) updateNoteText(i, e.target.value);
    });
  });
  container.querySelectorAll('button[data-remove-note]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const i = parseInt(e.currentTarget.dataset.removeNote, 10);
      if (!isNaN(i)) removeNote(i);
    });
  });
}

function addNote() {
  if (!currentScenario) return;
  if (!currentScenario.operator_notes) currentScenario.operator_notes = [];
  if (currentScenario.operator_notes.length >= 3) {
    showToast('Maximum 3 operator notes allowed per specification.', 'error');
    return;
  }
  currentScenario.operator_notes.push('Panel maintenance notice from noon to 2 PM: usable solar drops to 25%.');
  renderNotesList(currentScenario.operator_notes);
}

function removeNote(idx) {
  if (!currentScenario || !currentScenario.operator_notes) return;
  currentScenario.operator_notes.splice(idx, 1);
  renderNotesList(currentScenario.operator_notes);
}

function updateNoteText(idx, val) {
  if (!currentScenario || !currentScenario.operator_notes) return;
  currentScenario.operator_notes[idx] = val;
}

/**
 * Validate and Collect Payload
 */
function collectScenarioPayload() {
  if (!currentScenario) return null;
  const payload = JSON.parse(JSON.stringify(currentScenario));

  payload.scenario_id = document.getElementById('scenarioIdInput').value.trim() || 'SCENARIO-01';
  
  const cap = parseFloat(document.getElementById('batteryCapacity').value);
  const init = parseFloat(document.getElementById('batteryInitial').value);
  const min = parseFloat(document.getElementById('batteryMin').value);
  const maxChg = parseFloat(document.getElementById('batteryMaxCharge').value);
  const maxDis = parseFloat(document.getElementById('batteryMaxDischarge').value);

  // Client-side guard validation aligned with Pydantic contract
  if (isNaN(cap) || cap <= 0) {
    showToast('Battery capacity must be greater than 0 kWh.', 'error');
    return null;
  }
  if (isNaN(init) || init < 0 || init > cap) {
    showToast(`Initial SoC must be between 0 and capacity (${cap} kWh).`, 'error');
    return null;
  }
  if (isNaN(min) || min < 0 || min > cap) {
    showToast(`Minimum reserve must be between 0 and capacity (${cap} kWh).`, 'error');
    return null;
  }
  if (isNaN(maxChg) || maxChg < 0) {
    showToast('Max charge rate must be non-negative.', 'error');
    return null;
  }
  if (isNaN(maxDis) || maxDis < 0) {
    showToast('Max discharge rate must be non-negative.', 'error');
    return null;
  }

  payload.battery.capacity_kwh = cap;
  payload.battery.initial_energy_kwh = init;
  payload.battery.minimum_energy_kwh = min;
  payload.battery.max_charge_kwh_per_hour = maxChg;
  payload.battery.max_discharge_kwh_per_hour = maxDis;

  const noteElements = document.querySelectorAll('.note-text');
  payload.operator_notes = Array.from(noteElements).map(el => el.value.trim()).filter(Boolean);

  if (payload.operator_notes.length === 0) {
    showToast('At least one operator note is required.', 'error');
    return null;
  }
  if (payload.operator_notes.length > 3) {
    showToast('Maximum 3 operator notes allowed.', 'error');
    return null;
  }

  return payload;
}

/**
 * Run Optimization API Call
 */
async function runOptimization() {
  const payload = collectScenarioPayload();
  if (!payload) return;

  const btn = document.getElementById('btnRunOptimization');
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> <span class="btn-text">Optimizing Dispatch...</span>`;

  document.getElementById('requestJson').innerText = JSON.stringify(payload, null, 2);

  try {
    const start = performance.now();
    const res = await fetch('/optimize-energy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const dur = Math.round(performance.now() - start);

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const msg = errData.detail ? JSON.stringify(errData.detail) : `HTTP ${res.status}`;
      showToast(`Optimization Failed: ${msg}`, 'error');
      return;
    }

    const data = await res.json();
    renderResults(data, payload, dur);
    document.getElementById('responseJson').innerText = JSON.stringify(data, null, 2);
    showToast(`Optimal plan computed in ${dur}ms`, 'success');
  } catch (err) {
    console.error('Fetch error:', err);
    showToast(`Network Error: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span class="btn-icon">⚡</span> <span class="btn-text">RUN LLM ENERGY OPTIMIZATION</span>`;
  }
}

/**
 * Render Optimization Results
 */
function renderResults(data, payload, latencyMs) {
  lastPlan = data.hourly_plan;
  lastHoursInput = payload.hours;
  lastData = data;

  // 1. Calculate Baseline Cost (Solar direct + Grid fallback, Battery idle)
  let baselineCost = 0;
  payload.hours.forEach(h => {
    const directSolar = Math.min(h.solar_kwh, h.demand_kwh);
    const gridNeeded = Math.max(0, h.demand_kwh - directSolar);
    baselineCost += gridNeeded * h.tariff_bdt_per_kwh;
  });

  const savings = baselineCost - data.total_cost_bdt;
  const savingsPct = baselineCost > 0 ? (savings / baselineCost) * 100 : 0;

  // 2. Executive KPI Cards
  document.getElementById('kpiCost').innerText = `৳${data.total_cost_bdt.toLocaleString()}`;
  if (savings > 0) {
    document.getElementById('kpiSavings').innerHTML = `Saved <strong style="color:var(--accent-emerald)">৳${Math.round(savings).toLocaleString()}</strong> (${savingsPct.toFixed(1)}%) vs Baseline`;
  } else {
    document.getElementById('kpiSavings').innerText = 'Neutral vs baseline dispatch';
  }

  document.getElementById('kpiGrid').innerText = `${data.total_grid_kwh.toLocaleString()} kWh`;
  document.getElementById('kpiPeak').innerText = `${data.peak_grid_kwh.toLocaleString()} kW`;
  
  const activeDirectives = data.directive_interpretation.filter(d => d.applies && d.directive_type !== 'no_op').length;
  document.getElementById('kpiDirectives').innerText = `${activeDirectives} Active / ${data.directive_interpretation.length} Notes`;
  document.getElementById('kpiLatency').innerText = `Engine Latency: ${latencyMs}ms`;

  // 3. Strategy Summary
  document.getElementById('summaryText').innerText = data.plan_summary || 'Optimal schedule computed.';

  // 4. Directives Breakdown with Original Note Quotes
  const dirContainer = document.getElementById('directivesContainer');
  dirContainer.innerHTML = '';
  
  const countBadge = document.getElementById('directiveCountBadge');
  if (countBadge) {
    countBadge.innerText = `${activeDirectives} Active`;
  }

  data.directive_interpretation.forEach(d => {
    const card = document.createElement('div');
    const typeClass = d.directive_type.replace(/_/g, '-');
    card.className = `directive-card ${typeClass} ${d.directive_type === 'no_op' ? 'no-op' : ''}`;
    
    let adjText = '';
    if (d.structured_adjustment) {
      const adj = d.structured_adjustment;
      const chips = [];
      if (adj.hours && adj.hours.length > 0) chips.push(`Hours: [${adj.hours.join(', ')}]`);
      if (adj.factor !== undefined) chips.push(`Solar Factor: ${(adj.factor * 100).toFixed(0)}%`);
      if (adj.minimum_energy_kwh !== undefined) chips.push(`Reserve Floor: ${adj.minimum_energy_kwh} kWh`);
      if (adj.max_grid_kwh !== undefined) chips.push(`Grid Ceiling: ${adj.max_grid_kwh} kW`);

      if (chips.length > 0) {
        adjText = `
          <div class="directive-chips">
            ${chips.map(c => `<span class="badge-hour">${escapeHtml(c)}</span>`).join('')}
          </div>
        `;
      }
    }

    const originalNote = (payload.operator_notes && payload.operator_notes[d.note_index]) || '';
    const originalQuote = originalNote ? `<div class="directive-original-note">"${escapeHtml(originalNote)}"</div>` : '';

    card.innerHTML = `
      <div class="directive-top">
        <span class="note-index-badge">Note [${d.note_index}]</span>
        <span class="directive-tag tag-${d.directive_type}">${escapeHtml(d.directive_type)}</span>
      </div>
      ${originalQuote}
      <div class="directive-explanation">${escapeHtml(d.explanation)}</div>
      ${adjText}
    `;
    dirContainer.appendChild(card);
  });

  // 5. Render 24h Interactive Chart
  renderChart(lastPlan, lastHoursInput, null);

  // 6. Render Hourly Plan Table with Summary Foot
  renderTable(lastPlan, lastHoursInput, data);
}

/**
 * Canvas Chart Drawing Routine with High-DPI, Solar Forecast, and Hover Highlights
 */
function renderChart(plan, hoursInput, activeHour = null) {
  const canvas = document.getElementById('dispatchChart');
  if (!canvas || !plan || !hoursInput) return;

  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();

  // Resize internal buffer for crisp display
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.resetTransform ? ctx.resetTransform() : ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.scale(dpr, dpr);

  const W = rect.width;
  const H = rect.height;
  const pad = { top: 25, right: 25, bottom: 35, left: 45 };
  const plotW = Math.max(10, W - pad.left - pad.right);
  const plotH = Math.max(10, H - pad.top - pad.bottom);

  ctx.clearRect(0, 0, W, H);

  // Find max value for Y-axis scale across all series
  let maxVal = 50;
  for (let h = 0; h < 24; h++) {
    const p = plan[h];
    const inp = hoursInput[h];
    maxVal = Math.max(maxVal, p.grid_kwh, p.solar_used_kwh, inp.solar_kwh, inp.demand_kwh, p.battery_energy_after_kwh);
  }
  maxVal = Math.ceil(maxVal / 50) * 50;

  // Grid lines & Y-Axis Labels
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
  ctx.lineWidth = 1;
  const yTicks = 4;
  ctx.font = '10px "JetBrains Mono", monospace';
  ctx.fillStyle = '#94a3b8';
  ctx.textAlign = 'right';

  for (let i = 0; i <= yTicks; i++) {
    const yVal = Math.round((maxVal / yTicks) * i);
    const yPos = pad.top + plotH - (plotH * (yVal / maxVal));
    ctx.beginPath();
    ctx.moveTo(pad.left, yPos);
    ctx.lineTo(pad.left + plotW, yPos);
    ctx.stroke();
    ctx.fillText(`${yVal}`, pad.left - 8, yPos + 3);
  }

  // X-axis ticks
  const step = W < 450 ? 4 : 2;
  ctx.textAlign = 'center';
  for (let h = 0; h < 24; h += step) {
    const xPos = pad.left + (plotW * (h / 23));
    ctx.fillText(`${h}h`, xPos, H - 12);
  }

  // Coordinate mappers
  const getX = (h) => pad.left + (plotW * (h / 23));
  const getY = (val) => pad.top + plotH - (plotH * (Math.max(0, val) / maxVal));

  // 1. Draw Solar Forecast (Amber Dashed Reference Line)
  ctx.beginPath();
  ctx.setLineDash([3, 3]);
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.45)';
  ctx.lineWidth = 1.5;
  for (let h = 0; h < 24; h++) {
    const x = getX(h);
    const y = getY(hoursInput[h].solar_kwh);
    if (h === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // 2. Draw Demand (Dashed White Line)
  ctx.beginPath();
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.55)';
  ctx.lineWidth = 1.5;
  for (let h = 0; h < 24; h++) {
    const x = getX(h);
    const y = getY(hoursInput[h].demand_kwh);
    if (h === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // 3. Draw Solar Used Area (Warm Gold/Amber fill + line)
  ctx.beginPath();
  ctx.fillStyle = 'rgba(245, 158, 11, 0.16)';
  ctx.strokeStyle = '#f59e0b';
  ctx.lineWidth = 2;
  ctx.moveTo(getX(0), getY(0));
  for (let h = 0; h < 24; h++) {
    ctx.lineTo(getX(h), getY(plan[h].solar_used_kwh));
  }
  ctx.lineTo(getX(23), getY(0));
  ctx.closePath();
  ctx.fill();

  ctx.beginPath();
  for (let h = 0; h < 24; h++) {
    const x = getX(h);
    const y = getY(plan[h].solar_used_kwh);
    if (h === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // 4. Draw Grid Import Line (Electric Blue/Cyan)
  ctx.beginPath();
  ctx.strokeStyle = '#0ea5e9';
  ctx.lineWidth = 2.5;
  for (let h = 0; h < 24; h++) {
    const x = getX(h);
    const y = getY(plan[h].grid_kwh);
    if (h === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // 5. Draw Battery SoC Line (Vibrant Emerald)
  ctx.beginPath();
  ctx.strokeStyle = '#10b981';
  ctx.lineWidth = 2;
  for (let h = 0; h < 24; h++) {
    const x = getX(h);
    const y = getY(plan[h].battery_energy_after_kwh);
    if (h === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // 6. Active Hour Highlight Line & Dots
  if (activeHour !== null && activeHour >= 0 && activeHour < 24) {
    const hX = getX(activeHour);

    // Vertical dashed marker line
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(14, 165, 233, 0.75)';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.moveTo(hX, pad.top);
    ctx.lineTo(hX, pad.top + plotH);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw point markers
    const drawDot = (yVal, color) => {
      ctx.beginPath();
      ctx.arc(hX, getY(yVal), 4.5, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = '#070a12';
      ctx.stroke();
    };

    drawDot(hoursInput[activeHour].demand_kwh, '#ffffff');
    drawDot(hoursInput[activeHour].solar_kwh, '#f59e0b');
    drawDot(plan[activeHour].solar_used_kwh, '#f59e0b');
    drawDot(plan[activeHour].grid_kwh, '#0ea5e9');
    drawDot(plan[activeHour].battery_energy_after_kwh, '#10b981');
  }
}

/**
 * Chart Mouse & Touch Tooltip Handlers
 */
function handleChartMove(e) {
  if (!lastPlan || !lastHoursInput) return;
  const canvas = document.getElementById('dispatchChart');
  const tooltip = document.getElementById('chartTooltip');
  const rect = canvas.getBoundingClientRect();

  const mouseX = e.clientX - rect.left;
  const pad = { left: 45, right: 25 };
  const plotW = rect.width - pad.left - pad.right;

  if (mouseX < pad.left || mouseX > rect.width - pad.right) {
    handleChartLeave();
    return;
  }

  const ratio = (mouseX - pad.left) / plotW;
  const hour = Math.min(23, Math.max(0, Math.round(ratio * 23)));
  hoveredHour = hour;

  renderChart(lastPlan, lastHoursInput, hour);
  highlightTableRow(hour);

  // Update Tooltip
  const p = lastPlan[hour];
  const inp = lastHoursInput[hour];
  const hourlyCost = (p.grid_kwh * inp.tariff_bdt_per_kwh).toFixed(1);

  tooltip.style.display = 'block';
  tooltip.innerHTML = `
    <div style="font-weight:700; color:var(--accent-cyan); margin-bottom:0.3rem; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:0.25rem;">
      Hour ${hour}:00 &bull; Tariff: ৳${inp.tariff_bdt_per_kwh} / kWh
    </div>
    <div style="display:flex; justify-content:space-between; gap:1.2rem;">
      <span style="color:#ffffff;">⚡ Demand:</span>
      <strong>${inp.demand_kwh.toFixed(1)} kWh</strong>
    </div>
    <div style="display:flex; justify-content:space-between; gap:1.2rem;">
      <span style="color:#f59e0b;">☀️ Solar:</span>
      <strong>Used ${p.solar_used_kwh.toFixed(1)} <span style="font-size:0.7em; color:var(--text-dim)">(Fcst ${inp.solar_kwh.toFixed(1)})</span></strong>
    </div>
    <div style="display:flex; justify-content:space-between; gap:1.2rem;">
      <span style="color:#0ea5e9;">🔌 Grid Import:</span>
      <strong>${p.grid_kwh.toFixed(1)} kWh</strong>
    </div>
    <div style="display:flex; justify-content:space-between; gap:1.2rem;">
      <span style="color:#10b981;">🔋 Battery SoC:</span>
      <strong>${p.battery_energy_after_kwh.toFixed(1)} kWh</strong>
    </div>
    <div style="display:flex; justify-content:space-between; gap:1.2rem; margin-top:0.2rem; border-top:1px dashed rgba(255,255,255,0.08); padding-top:0.2rem;">
      <span style="color:var(--text-dim);">Action:</span>
      <strong style="color:${p.battery_action === 'charge' ? '#34d399' : (p.battery_action === 'discharge' ? '#fbbf24' : '#94a3b8')}">${p.battery_action.toUpperCase()} (${p.battery_kwh > 0 ? p.battery_kwh.toFixed(1) + ' kW' : '0 kW'})</strong>
    </div>
    <div style="display:flex; justify-content:space-between; gap:1.2rem;">
      <span style="color:var(--text-dim);">Hourly Cost:</span>
      <strong style="color:#38bdf8;">৳${hourlyCost}</strong>
    </div>
  `;

  // Position tooltip safely within canvas bounds
  const tooltipRect = tooltip.getBoundingClientRect();
  let leftPos = mouseX + 15;
  if (leftPos + tooltipRect.width > rect.width) {
    leftPos = mouseX - tooltipRect.width - 15;
  }
  let topPos = 15;

  tooltip.style.left = `${Math.max(10, leftPos)}px`;
  tooltip.style.top = `${topPos}px`;
}

function handleChartTouch(e) {
  if (e.touches && e.touches[0]) {
    handleChartMove(e.touches[0]);
  }
}

function handleChartLeave() {
  hoveredHour = null;
  const tooltip = document.getElementById('chartTooltip');
  if (tooltip) tooltip.style.display = 'none';
  if (lastPlan && lastHoursInput) {
    renderChart(lastPlan, lastHoursInput, null);
  }
  highlightTableRow(null);
}

function highlightTableRow(hour) {
  document.querySelectorAll('#tableBody tr').forEach((tr, h) => {
    if (hour !== null && h === hour) {
      tr.classList.add('row-active');
    } else {
      tr.classList.remove('row-active');
    }
  });
}

/**
 * Render Hourly Plan Data Table with Summary Foot
 */
function renderTable(plan, hoursInput, fullData) {
  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = '';

  let sumDemand = 0;
  let sumSolar = 0;
  let sumGrid = 0;
  let netBattery = 0;

  plan.forEach((p, h) => {
    const inp = hoursInput[h];
    sumDemand += inp.demand_kwh;
    sumSolar += p.solar_used_kwh;
    sumGrid += p.grid_kwh;
    netBattery += (p.battery_action === 'charge' ? p.battery_kwh : (p.battery_action === 'discharge' ? -p.battery_kwh : 0));

    const tr = document.createElement('tr');
    tr.id = `row-hour-${h}`;
    const actionClass = `action-${p.battery_action}`;
    
    tr.innerHTML = `
      <td class="sticky-col col-hour"><strong>${String(p.hour).padStart(2, '0')}h</strong></td>
      <td class="col-num">${inp.demand_kwh.toFixed(1)}</td>
      <td class="col-num"><span style="color: #f59e0b">${p.solar_used_kwh.toFixed(1)}</span></td>
      <td class="col-num"><span style="color: ${p.grid_kwh === 0 ? '#10b981' : '#38bdf8'}; font-weight: 600">${p.grid_kwh.toFixed(1)}</span></td>
      <td class="col-action"><span class="badge-action ${actionClass}">${p.battery_action}</span></td>
      <td class="col-num">${p.battery_kwh > 0 ? p.battery_kwh.toFixed(1) : '-'}</td>
      <td class="col-num"><span style="color: #10b981; font-weight: 600">${p.battery_energy_after_kwh.toFixed(1)}</span></td>
      <td class="col-num" style="color: #cbd5e1">৳${inp.tariff_bdt_per_kwh}</td>
    `;

    // Row hover interacts with chart
    tr.addEventListener('mouseenter', () => {
      hoveredHour = h;
      renderChart(lastPlan, lastHoursInput, h);
      tr.classList.add('row-active');
    });
    tr.addEventListener('mouseleave', () => {
      hoveredHour = null;
      renderChart(lastPlan, lastHoursInput, null);
      tr.classList.remove('row-active');
    });

    tbody.appendChild(tr);
  });

  // Table Footer Summary Row
  const tfoot = document.getElementById('tableFoot');
  if (tfoot) {
    const finalSoc = plan.length > 0 ? plan[plan.length - 1].battery_energy_after_kwh : 0;
    const totalCost = fullData ? fullData.total_cost_bdt : 0;

    tfoot.innerHTML = `
      <tr>
        <td class="sticky-col col-hour"><strong>TOTAL</strong></td>
        <td class="col-num">${sumDemand.toFixed(1)}</td>
        <td class="col-num" style="color:#f59e0b">${sumSolar.toFixed(1)}</td>
        <td class="col-num" style="color:#38bdf8; font-weight:700">${sumGrid.toFixed(1)}</td>
        <td class="col-action"><span class="badge-action action-idle">NEUTRAL</span></td>
        <td class="col-num">${Math.abs(netBattery) < 0.001 ? '0.0' : netBattery.toFixed(1)}</td>
        <td class="col-num" style="color:#10b981; font-weight:700">${finalSoc.toFixed(1)}</td>
        <td class="col-num" style="color:#38bdf8; font-weight:800">৳${totalCost.toLocaleString()}</td>
      </tr>
    `;
  }
}

/**
 * Export Hourly Schedule as CSV
 */
function exportCsv() {
  if (!lastPlan || !lastHoursInput) {
    showToast('Run optimization first to generate schedule.', 'error');
    return;
  }

  const scenarioId = (currentScenario && currentScenario.scenario_id) || 'scenario';
  const headers = [
    'Hour',
    'Demand_kWh',
    'Solar_Forecast_kWh',
    'Solar_Used_kWh',
    'Grid_Import_kWh',
    'Battery_Action',
    'Battery_Rate_kW',
    'Battery_SoC_After_kWh',
    'Tariff_BDT_per_kWh',
    'Hourly_Cost_BDT'
  ];

  const rows = lastPlan.map((p, h) => {
    const inp = lastHoursInput[h];
    const cost = (p.grid_kwh * inp.tariff_bdt_per_kwh).toFixed(2);
    return [
      p.hour,
      inp.demand_kwh.toFixed(2),
      inp.solar_kwh.toFixed(2),
      p.solar_used_kwh.toFixed(2),
      p.grid_kwh.toFixed(2),
      p.battery_action,
      p.battery_kwh.toFixed(2),
      p.battery_energy_after_kwh.toFixed(2),
      inp.tariff_bdt_per_kwh.toFixed(2),
      cost
    ].join(',');
  });

  const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows].join('\n');
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `gridwise_schedule_${scenarioId}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  showToast(`Schedule exported as CSV: gridwise_schedule_${scenarioId}.csv`, 'success');
}

/**
 * Download Raw JSON helper
 */
function downloadJson(elementId, filename) {
  const el = document.getElementById(elementId);
  if (!el || !el.innerText) return;

  const blob = new Blob([el.innerText], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  showToast(`Downloaded ${filename}`, 'success');
}

/**
 * Copy JSON Utility
 */
async function copyJson(id) {
  const el = document.getElementById(id);
  if (!el) return;
  try {
    await navigator.clipboard.writeText(el.innerText);
    showToast('Payload copied to clipboard!', 'success');
  } catch (err) {
    const range = document.createRange();
    range.selectNodeContents(el);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    try {
      document.execCommand('copy');
      showToast('Payload copied to clipboard!', 'success');
    } catch (e) {
      showToast('Failed to copy to clipboard', 'error');
    }
    sel.removeAllRanges();
  }
}

/**
 * Helper: Escape HTML to prevent XSS
 */
function escapeHtml(str) {
  if (typeof str !== 'string') return str;
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
}
