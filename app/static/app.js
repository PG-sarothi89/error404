// GridWise LLM Energy Optimizer Dashboard Application Logic
let currentScenario = null;
let publicCases = [];

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', async () => {
  await loadPublicCases();
  setupEventListeners();
  // Automatically select SAMPLE-01 on first load
  selectPreset(0);
});

// Load public cases from server or embed fallback
async function loadPublicCases() {
  try {
    const res = await fetch('/api/scenarios');
    if (res.ok) {
      const data = await res.json();
      publicCases = data.cases || [];
    }
  } catch (err) {
    console.warn('Failed to load scenarios from API, using default sample');
  }

  // Render Preset Buttons
  const presetContainer = document.getElementById('presetContainer');
  presetContainer.innerHTML = '';
  publicCases.forEach((c, idx) => {
    const btn = document.createElement('button');
    btn.className = `preset-chip ${idx === 0 ? 'active' : ''}`;
    btn.innerText = c.id || `CASE-${idx+1}`;
    btn.title = c.label || '';
    btn.onclick = () => selectPreset(idx);
    presetContainer.appendChild(btn);
  });
}

function selectPreset(index) {
  if (!publicCases[index]) return;
  const c = publicCases[index];
  currentScenario = JSON.parse(JSON.stringify(c.input));

  // Update preset chip styles
  document.querySelectorAll('.preset-chip').forEach((el, i) => {
    el.classList.toggle('active', i === index);
  });

  populateForm(currentScenario);
  runOptimization();
}

function populateForm(scenario) {
  document.getElementById('scenarioIdInput').value = scenario.scenario_id || 'DEMO-01';
  document.getElementById('batteryCapacity').value = scenario.battery.capacity_kwh;
  document.getElementById('batteryInitial').value = scenario.battery.initial_energy_kwh;
  document.getElementById('batteryMin').value = scenario.battery.minimum_energy_kwh;
  document.getElementById('batteryMaxCharge').value = scenario.battery.max_charge_kwh_per_hour;
  document.getElementById('batteryMaxDischarge').value = scenario.battery.max_discharge_kwh_per_hour;

  renderNotesList(scenario.operator_notes || []);
}

function renderNotesList(notes) {
  const container = document.getElementById('notesContainer');
  container.innerHTML = '';
  notes.forEach((note, idx) => {
    const div = document.createElement('div');
    div.className = 'note-item';
    div.innerHTML = `
      <div class="note-header">
        <span class="note-index-badge">Note [${idx}]</span>
        ${notes.length > 1 ? `<button type="button" class="btn-remove-note" onclick="removeNote(${idx})">&times; Remove</button>` : ''}
      </div>
      <textarea class="form-textarea note-text" rows="2" onchange="updateNoteText(${idx}, this.value)">${note}</textarea>
    `;
    container.appendChild(div);
  });
}

function addNote() {
  if (!currentScenario) return;
  if (!currentScenario.operator_notes) currentScenario.operator_notes = [];
  if (currentScenario.operator_notes.length >= 3) {
    alert('Maximum 3 operator notes allowed per scenario specification.');
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

function setupEventListeners() {
  document.getElementById('btnAddNote').addEventListener('click', addNote);
  document.getElementById('btnRunOptimization').addEventListener('click', runOptimization);
}

function collectScenarioPayload() {
  if (!currentScenario) return null;
  const payload = JSON.parse(JSON.stringify(currentScenario));

  payload.scenario_id = document.getElementById('scenarioIdInput').value.trim();
  payload.battery.capacity_kwh = parseFloat(document.getElementById('batteryCapacity').value);
  payload.battery.initial_energy_kwh = parseFloat(document.getElementById('batteryInitial').value);
  payload.battery.minimum_energy_kwh = parseFloat(document.getElementById('batteryMin').value);
  payload.battery.max_charge_kwh_per_hour = parseFloat(document.getElementById('batteryMaxCharge').value);
  payload.battery.max_discharge_kwh_per_hour = parseFloat(document.getElementById('batteryMaxDischarge').value);

  const noteElements = document.querySelectorAll('.note-text');
  payload.operator_notes = Array.from(noteElements).map(el => el.value.trim()).filter(Boolean);

  return payload;
}

// Run Optimization API Call
async function runOptimization() {
  const payload = collectScenarioPayload();
  if (!payload) return;

  const btn = document.getElementById('btnRunOptimization');
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Running Pipeline...`;

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
      const errData = await res.json();
      alert(`Optimization Error (${res.status}): ${JSON.stringify(errData)}`);
      return;
    }

    const data = await res.json();
    renderResults(data, payload, dur);
    document.getElementById('responseJson').innerText = JSON.stringify(data, null, 2);
  } catch (err) {
    console.error('Fetch error:', err);
    alert('Failed to connect to /optimize-energy API: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>⚡</span> Run LLM Energy Optimization`;
  }
}

function renderResults(data, payload, latencyMs) {
  // 1. KPI Cards
  document.getElementById('kpiCost').innerText = `৳${data.total_cost_bdt.toLocaleString()}`;
  document.getElementById('kpiGrid').innerText = `${data.total_grid_kwh.toLocaleString()} kWh`;
  document.getElementById('kpiPeak').innerText = `${data.peak_grid_kwh.toLocaleString()} kW`;
  document.getElementById('kpiDirectives').innerText = `${data.directive_interpretation.length} Notes`;
  document.getElementById('kpiLatency').innerText = `Latency: ${latencyMs}ms`;

  // 2. Summary
  document.getElementById('summaryText').innerText = data.plan_summary || 'Optimal schedule computed.';

  // 3. Directive Interpretation Cards
  const dirContainer = document.getElementById('directivesContainer');
  dirContainer.innerHTML = '';
  data.directive_interpretation.forEach(d => {
    const card = document.createElement('div');
    const typeClass = d.directive_type.replace('_', '-');
    card.className = `directive-card ${typeClass} ${d.directive_type === 'no_op' ? 'no-op' : ''}`;
    
    let adjText = '';
    if (d.structured_adjustment) {
      const adj = d.structured_adjustment;
      const hoursBadge = adj.hours ? `Hours: [${adj.hours.join(', ')}]` : '';
      const factorBadge = adj.factor !== undefined ? `Factor: ${(adj.factor * 100).toFixed(0)}%` : '';
      const reserveBadge = adj.minimum_energy_kwh !== undefined ? `Min Reserve: ${adj.minimum_energy_kwh} kWh` : '';
      const gridBadge = adj.max_grid_kwh !== undefined ? `Grid Cap: ${adj.max_grid_kwh} kWh` : '';
      
      adjText = `
        <div class="directive-chips">
          ${hoursBadge ? `<span class="badge-hour">${hoursBadge}</span>` : ''}
          ${factorBadge ? `<span class="badge-hour">${factorBadge}</span>` : ''}
          ${reserveBadge ? `<span class="badge-hour">${reserveBadge}</span>` : ''}
          ${gridBadge ? `<span class="badge-hour">${gridBadge}</span>` : ''}
        </div>
      `;
    }

    card.innerHTML = `
      <div class="directive-top">
        <span class="note-index-badge">Note [${d.note_index}]</span>
        <span class="directive-tag tag-${d.directive_type}">${d.directive_type}</span>
      </div>
      <div class="directive-explanation">${d.explanation}</div>
      ${adjText}
    `;
    dirContainer.appendChild(card);
  });

  // 4. Render 24h Interactive Chart
  renderChart(data.hourly_plan, payload.hours);

  // 5. Render Table
  renderTable(data.hourly_plan, payload.hours);
}

// Canvas-based Lightweight Multi-Series Chart
function renderChart(plan, hoursInput) {
  const canvas = document.getElementById('dispatchChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();

  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const W = rect.width;
  const H = rect.height;
  const pad = { top: 25, right: 25, bottom: 35, left: 45 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  ctx.clearRect(0, 0, W, H);

  // Find max value for Y-axis scale
  let maxVal = 50;
  for (let h = 0; h < 24; h++) {
    const p = plan[h];
    const inp = hoursInput[h];
    maxVal = Math.max(maxVal, p.grid_kwh, p.solar_used_kwh, inp.demand_kwh, p.battery_energy_after_kwh);
  }
  maxVal = Math.ceil(maxVal / 50) * 50;

  // Grid lines
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

  // X-axis ticks (every 2 hours)
  ctx.textAlign = 'center';
  for (let h = 0; h < 24; h += 2) {
    const xPos = pad.left + (plotW * (h / 23));
    ctx.fillText(`${h}h`, xPos, H - 12);
  }

  // Helper coordinate mapper
  const getX = (h) => pad.left + (plotW * (h / 23));
  const getY = (val) => pad.top + plotH - (plotH * (Math.max(0, val) / maxVal));

  // 1. Draw Demand (Dashed Slate line)
  ctx.beginPath();
  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
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
  ctx.fillStyle = 'rgba(245, 158, 11, 0.15)';
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

  // 3. Draw Grid Import Line (Cyan)
  ctx.beginPath();
  ctx.strokeStyle = '#06b6d4';
  ctx.lineWidth = 2.5;
  for (let h = 0; h < 24; h++) {
    const x = getX(h);
    const y = getY(plan[h].grid_kwh);
    if (h === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // 4. Draw Battery State of Charge Line (Emerald)
  ctx.beginPath();
  ctx.strokeStyle = '#10b981';
  ctx.lineWidth = 2;
  for (let h = 0; h < 24; h++) {
    const x = getX(h);
    const y = getY(plan[h].battery_energy_after_kwh);
    if (h === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

function renderTable(plan, hoursInput) {
  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = '';
  plan.forEach((p, h) => {
    const tr = document.createElement('tr');
    const inp = hoursInput[h];
    const actionClass = `action-${p.battery_action}`;
    
    tr.innerHTML = `
      <td><strong>${p.hour}</strong></td>
      <td>${inp.demand_kwh.toFixed(1)}</td>
      <td><span style="color: #f59e0b">${p.solar_used_kwh.toFixed(1)}</span></td>
      <td><span style="color: #06b6d4; font-weight: 600">${p.grid_kwh.toFixed(1)}</span></td>
      <td><span class="badge-action ${actionClass}">${p.battery_action}</span></td>
      <td>${p.battery_kwh > 0 ? p.battery_kwh.toFixed(1) : '-'}</td>
      <td><span style="color: #10b981; font-weight: 600">${p.battery_energy_after_kwh.toFixed(1)}</span></td>
      <td style="color: #94a3b8">৳${inp.tariff_bdt_per_kwh}</td>
    `;
    tbody.appendChild(tr);
  });
}

function copyJson(id) {
  const el = document.getElementById(id);
  navigator.clipboard.writeText(el.innerText);
  alert('Copied to clipboard!');
}
window.copyJson = copyJson;
