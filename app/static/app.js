/**
 * GridWise 2.0 · Smart Campus Energy Optimizer
 * Frontend Application Logic & Responsive Dashboard Controller
 */

let currentScenario = null;
let publicCases = [];
let lastPlan = null;
let lastHoursInput = null;
let hoveredHour = null;

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await loadPublicCases();
  // Automatically select the first preset
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

  // Chart interactivity (mouse & touch)
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
 * Toast Notification System
 */
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  const icon = type === 'success' ? '✅' : (type === 'error' ? '❌' : 'ℹ️');
  toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
  
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
  runOptimization();
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
  notes.forEach((note, idx) => {
    const div = document.createElement('div');
    div.className = 'note-item';
    div.innerHTML = `
      <div class="note-header">
        <span class="note-index-badge">Operator Note [${idx}]</span>
        ${notes.length > 1 ? `<button type="button" class="btn-remove-note" onclick="removeNote(${idx})" aria-label="Remove note ${idx}">&times; Remove</button>` : ''}
      </div>
      <textarea class="form-textarea note-text" rows="2" aria-label="Operator note ${idx}" onchange="updateNoteText(${idx}, this.value)">${escapeHtml(note)}</textarea>
    `;
    container.appendChild(div);
  });
}

function addNote() {
  if (!currentScenario) return;
  if (!currentScenario.operator_notes) currentScenario.operator_notes = [];
  if (currentScenario.operator_notes.length >= 3) {
    showToast('Maximum 3 operator notes allowed per specification.', 'error');
    return;
  }
  currentScenario.operator_notes.push('New operator notice here.');
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

window.removeNote = removeNote;
window.updateNoteText = updateNoteText;

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

  // Client-side guard validation
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
  if (min > init) {
    showToast(`Minimum reserve (${min} kWh) cannot exceed initial SoC (${init} kWh).`, 'error');
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
    showToast(`Optimization completed in ${dur}ms`, 'success');
  } catch (err) {
    console.error('Fetch error:', err);
    showToast(`Network Error: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span class="btn-icon">⚡</span> <span class="btn-text">Run LLM Energy Optimization</span>`;
  }
}

/**
 * Render Optimization Results
 */
function renderResults(data, payload, latencyMs) {
  lastPlan = data.hourly_plan;
  lastHoursInput = payload.hours;

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
  document.getElementById('kpiDirectives').innerText = `${data.directive_interpretation.length} Directives`;
  document.getElementById('kpiLatency').innerText = `Engine Latency: ${latencyMs}ms`;

  // 3. Strategy Summary
  document.getElementById('summaryText').innerText = data.plan_summary || 'Optimal schedule computed.';

  // 4. Directives Breakdown
  const dirContainer = document.getElementById('directivesContainer');
  dirContainer.innerHTML = '';
  
  const countBadge = document.getElementById('directiveCountBadge');
  if (countBadge) {
    countBadge.innerText = `${data.directive_interpretation.length} Active`;
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

    card.innerHTML = `
      <div class="directive-top">
        <span class="note-index-badge">Note [${d.note_index}]</span>
        <span class="directive-tag tag-${d.directive_type}">${escapeHtml(d.directive_type)}</span>
      </div>
      <div class="directive-explanation">${escapeHtml(d.explanation)}</div>
      ${adjText}
    `;
    dirContainer.appendChild(card);
  });

  // 5. Render 24h Interactive Chart
  renderChart(lastPlan, lastHoursInput, null);

  // 6. Render Hourly Plan Table
  renderTable(lastPlan, lastHoursInput);
}

/**
 * Canvas Chart Drawing Routine with High-DPI and Hover Highlights
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

  // Find max value for Y-axis scale
  let maxVal = 50;
  for (let h = 0; h < 24; h++) {
    const p = plan[h];
    const inp = hoursInput[h];
    maxVal = Math.max(maxVal, p.grid_kwh, p.solar_used_kwh, inp.demand_kwh, p.battery_energy_after_kwh);
  }
  maxVal = Math.ceil(maxVal / 50) * 50;

  // Grid lines & Y-Axis Labels
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
  ctx.lineWidth = 1;
  const yTicks = 4;
  ctx.font = '10px "JetBrains Mono", monospace';
  ctx.fillStyle = '#64748b';
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

  // X-axis ticks (every 2 or 3 hours depending on width)
  const step = W < 450 ? 4 : 2;
  ctx.textAlign = 'center';
  for (let h = 0; h < 24; h += step) {
    const xPos = pad.left + (plotW * (h / 23));
    ctx.fillText(`${h}h`, xPos, H - 12);
  }

  // Coordinate mappers
  const getX = (h) => pad.left + (plotW * (h / 23));
  const getY = (val) => pad.top + plotH - (plotH * (Math.max(0, val) / maxVal));

  // 1. Draw Demand (Dashed Light Line)
  ctx.beginPath();
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.45)';
  ctx.lineWidth = 1.5;
  for (let h = 0; h < 24; h++) {
    const x = getX(h);
    const y = getY(hoursInput[h].demand_kwh);
    if (h === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // 2. Draw Solar Used Area (Warm Gold/Amber)
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

  // 3. Draw Grid Import Line (Electric Blue/Cyan)
  ctx.beginPath();
  ctx.strokeStyle = '#0ea5e9';
  ctx.lineWidth = 2.5;
  for (let h = 0; h < 24; h++) {
    const x = getX(h);
    const y = getY(plan[h].grid_kwh);
    if (h === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // 4. Draw Battery SoC Line (Vibrant Emerald)
  ctx.beginPath();
  ctx.strokeStyle = '#10b981';
  ctx.lineWidth = 2;
  for (let h = 0; h < 24; h++) {
    const x = getX(h);
    const y = getY(plan[h].battery_energy_after_kwh);
    if (h === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // 5. Active Hour Highlight Line & Dots
  if (activeHour !== null && activeHour >= 0 && activeHour < 24) {
    const hX = getX(activeHour);

    // Vertical line
    ctx.beginPath();
    ctx.strokeStyle = 'rgba(6, 182, 212, 0.7)';
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
    drawDot(plan[activeHour].solar_used_kwh, '#f59e0b');
    drawDot(plan[activeHour].grid_kwh, '#06b6d4');
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

  // Update Tooltip
  const p = lastPlan[hour];
  const inp = lastHoursInput[hour];

  tooltip.style.display = 'block';
  tooltip.innerHTML = `
    <div style="font-weight:700; color:var(--accent-cyan); margin-bottom:0.25rem; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:0.2rem;">
      Hour ${hour}:00 &bull; Tariff: ৳${inp.tariff_bdt_per_kwh}
    </div>
    <div style="display:flex; justify-content:space-between; gap:1rem;">
      <span style="color:#ffffff;">⚡ Demand:</span>
      <strong>${inp.demand_kwh.toFixed(1)} kWh</strong>
    </div>
    <div style="display:flex; justify-content:space-between; gap:1rem;">
      <span style="color:#f59e0b;">☀️ Solar Used:</span>
      <strong>${p.solar_used_kwh.toFixed(1)} kWh</strong>
    </div>
    <div style="display:flex; justify-content:space-between; gap:1rem;">
      <span style="color:#06b6d4;">🔌 Grid Import:</span>
      <strong>${p.grid_kwh.toFixed(1)} kWh</strong>
    </div>
    <div style="display:flex; justify-content:space-between; gap:1rem;">
      <span style="color:#10b981;">🔋 Battery SoC:</span>
      <strong>${p.battery_energy_after_kwh.toFixed(1)} kWh</strong>
    </div>
    <div style="font-size:0.7rem; color:var(--text-dim); margin-top:0.2rem;">
      Action: <strong>${p.battery_action.toUpperCase()}</strong> (${p.battery_kwh > 0 ? p.battery_kwh.toFixed(1) + ' kWh' : '0 kWh'})
    </div>
  `;

  // Position tooltip safely within bounds
  const tooltipRect = tooltip.getBoundingClientRect();
  let leftPos = mouseX + 15;
  if (leftPos + tooltipRect.width > rect.width) {
    leftPos = mouseX - tooltipRect.width - 15;
  }
  let topPos = 20;

  tooltip.style.left = `${leftPos}px`;
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
}

/**
 * Render Hourly Plan Data Table
 */
function renderTable(plan, hoursInput) {
  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = '';
  plan.forEach((p, h) => {
    const tr = document.createElement('tr');
    const inp = hoursInput[h];
    const actionClass = `action-${p.battery_action}`;
    
    tr.innerHTML = `
      <td class="sticky-col col-hour"><strong>${String(p.hour).padStart(2, '0')}h</strong></td>
      <td class="col-num">${inp.demand_kwh.toFixed(1)}</td>
      <td class="col-num"><span style="color: #f59e0b">${p.solar_used_kwh.toFixed(1)}</span></td>
      <td class="col-num"><span style="color: ${p.grid_kwh === 0 ? '#10b981' : '#38bdf8'}; font-weight: 600">${p.grid_kwh.toFixed(1)}</span></td>
      <td class="col-action"><span class="badge-action ${actionClass}">${p.battery_action}</span></td>
      <td class="col-num">${p.battery_kwh > 0 ? p.battery_kwh.toFixed(1) : '-'}</td>
      <td class="col-num"><span style="color: #10b981; font-weight: 600">${p.battery_energy_after_kwh.toFixed(1)}</span></td>
      <td class="col-num" style="color: #94a3b8">৳${inp.tariff_bdt_per_kwh}</td>
    `;
    tbody.appendChild(tr);
  });

}

/**
 * Copy JSON Utility
 */
function copyJson(id) {
  const el = document.getElementById(id);
  if (!el) return;
  navigator.clipboard.writeText(el.innerText).then(() => {
    showToast('Payload copied to clipboard!', 'success');
  }).catch(() => {
    showToast('Failed to copy to clipboard', 'error');
  });
}
window.copyJson = copyJson;

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
