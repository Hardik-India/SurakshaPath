const map = L.map('map', { zoomControl: true }).setView([22.5726, 88.3639], 15);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; OpenStreetMap contributors',
  maxZoom: 19
}).addTo(map);

let selectedNodeId = null;
let currentNodeData = null;
let currentPredictionResult = null;
let markersByNodeId = {};
let selectionMarker = null;

const TIER_COLORS = {
  none: '#3b82f6',
  low: '#22c55e',
  moderate: '#f97316',
  high: '#ef4444'
};

// --- Heatmap ---
fetch('/api/heatmap')
  .then(res => res.json())
  .then(data => {
    const sortedVals = data.map(d => d[2]).sort((a, b) => a - b);
    const p95 = sortedVals[Math.floor(sortedVals.length * 0.95)] || Math.max(...sortedVals);
    const heatPoints = data.map(d => [d[0], d[1], Math.min(d[2], p95)]);

    L.heatLayer(heatPoints, {
      radius: 22, blur: 18, maxZoom: 17, max: p95,
      gradient: { 0.0: '#0000ff', 0.25: '#00ffff', 0.5: '#00ff00', 0.75: '#ffff00', 1.0: '#ff0000' }
    }).addTo(map);
  });

// --- Nodes + markers + stats bar + top-5 sidebar ---
fetch('/api/nodes')
  .then(res => res.json())
  .then(nodes => {
    nodes.forEach(node => {
      const color = TIER_COLORS[node.severity_tier];
      const radius = node.is_conflict_zone ? 8 : 5;

      const marker = L.circleMarker([node.lat, node.lon], {
        radius: radius, color: color, fillColor: color, fillOpacity: 0.85, weight: node.is_conflict_zone ? 2 : 1
      }).addTo(map);

      marker.bindTooltip(`${node.node_id}<br>${node.total_conflicts} conflicts`, { sticky: true });
      marker.on('click', () => openPanel(node));
      markersByNodeId[node.node_id] = { marker: marker, node: node };
    });

    const conflictZones = nodes.filter(n => n.is_conflict_zone);
    document.getElementById('stats-bar').innerText =
      `${nodes.length} junctions analyzed · ${conflictZones.length} conflict zones identified · 3 intervention types modeled`;

    const top5 = [...conflictZones].sort((a, b) => b.total_conflicts - a.total_conflicts).slice(0, 5);
    const listEl = document.getElementById('top5-list');
    listEl.innerHTML = top5.map((n, i) => `
      <div class="top5-item" data-node="${n.node_id}">
        <span class="top5-rank">#${i + 1}</span>
        <span class="top5-info">${n.node_id.slice(0, 22)}${n.node_id.length > 22 ? '…' : ''}<br><span class="top5-count">${n.total_conflicts} conflicts</span></span>
      </div>
    `).join('');

    document.querySelectorAll('.top5-item').forEach(item => {
      item.addEventListener('click', () => {
        const nodeId = item.getAttribute('data-node');
        const entry = markersByNodeId[nodeId];
        if (entry) {
          map.flyTo(entry.marker.getLatLng(), 17, { duration: 1 });
          openPanel(entry.node);
        }
      });
    });
  });

// --- Panel logic ---
function openPanel(node) {
  selectedNodeId = node.node_id;
  currentNodeData = node;
  currentPredictionResult = null;
  showSelectionPointer(node);
  document.getElementById('panel').classList.remove('hidden');
  document.getElementById('panel-title').innerText = node.node_id;
  document.getElementById('panel-result').innerHTML = '';

  function showSelectionPointer(node) {
  if (selectionMarker) {
    map.removeLayer(selectionMarker);
  }

  const icon = L.divIcon({
    className: 'selection-pointer-wrap',
    html: '<div class="selection-pointer"><div class="selection-ring"></div><div class="selection-dot"></div></div>',
    iconSize: [40, 40],
    iconAnchor: [20, 20]
  });

  selectionMarker = L.marker([node.lat, node.lon], { icon: icon, interactive: false, zIndexOffset: 1000 }).addTo(map);
}

  if (node.is_conflict_zone) {
    document.getElementById('panel-stats').innerHTML = `
      <div class="zone-badge zone-conflict">⚠ Conflict Zone</div>
      <div><span class="label">Baseline conflicts:</span> ${node.total_conflicts}</div>
      <div><span class="label">Severe conflicts:</span> ${node.severe_conflicts}</div>
      <div><span class="label">Has signal:</span> ${node.has_signal ? 'Yes' : 'No'}</div>
    `;

    fetchRecommendation(node.node_id);

    const formEl = document.getElementById('panel-form');
    formEl.classList.remove('hidden');
    formEl.style.display = 'block';

    const select = document.getElementById('intervention-select');
    const retimingOpt = select.querySelector('option[value="signal_retiming"]');
    const addSignalOpt = select.querySelector('option[value="add_signal"]');
    const turnRestrictOpt = select.querySelector('option[value="turn_restriction"]');

    retimingOpt.style.display = node.has_signal ? '' : 'none';
    addSignalOpt.style.display = node.has_signal ? 'none' : '';
    turnRestrictOpt.style.display = node.has_signal ? 'none' : '';
    select.value = 'speed_breaker';

  } else {
    document.getElementById('panel-recommendation').innerHTML = '';
    document.getElementById('panel-stats').innerHTML = `
      <div class="zone-badge zone-safe">✓ Non-Conflict Zone</div>
      <div><span class="label">Connected lanes:</span> ${node.num_lanes_total}</div>
      <div><span class="label">Has signal:</span> ${node.has_signal ? 'Yes' : 'No'}</div>
      <div class="reason-text">${node.reason}</div>
    `;
    const formEl = document.getElementById('panel-form');
    formEl.classList.add('hidden');
    formEl.style.display = 'none';
  }
}

function fetchRecommendation(nodeId) {
  const box = document.getElementById('panel-recommendation');
  box.innerHTML = `<div class="recommendation-loading">🔍 Analyzing best intervention...</div>`;

  fetch('/api/recommend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_id: nodeId })
  })
  .then(res => res.json())
  .then(result => {
    if (result.error) {
      box.innerHTML = `<div class="result-box result-error">${result.error}</div>`;
      return;
    }
    const icon = result.recommendation_type === 'positive' ? '✅' : '🔬';
    box.innerHTML = `
      <div class="recommendation-box recommendation-${result.recommendation_type}">
        <div class="recommendation-title">${icon} Recommended Action</div>
        <div class="recommendation-text">${result.narrative}</div>
      </div>
    `;
  })
  .catch(err => {
    box.innerHTML = `<div class="result-box result-error">Recommendation request failed: ${err}</div>`;
  });
}

document.getElementById('panel-close').addEventListener('click', () => {
  document.getElementById('panel').classList.add('hidden');
  if (selectionMarker) {
    map.removeLayer(selectionMarker);
    selectionMarker = null;
  }
});

// --- Predict button ---
document.getElementById('add-intervention-btn').addEventListener('click', () => {
  const intervention = document.getElementById('intervention-select').value;
  const btn = document.getElementById('add-intervention-btn');
  const btnText = document.getElementById('btn-text');
  const spinner = document.getElementById('btn-spinner');

  btn.disabled = true;
  btnText.innerText = 'Predicting';
  spinner.classList.remove('hidden');

  fetch('/api/predict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_id: selectedNodeId, intervention: intervention })
  })
  .then(res => res.json())
  .then(result => {
    btn.disabled = false;
    btnText.innerText = 'Add Intervention';
    spinner.classList.add('hidden');
    currentPredictionResult = result;
    renderResult(result);
  })
  .catch(err => {
    btn.disabled = false;
    btnText.innerText = 'Add Intervention';
    spinner.classList.add('hidden');
    document.getElementById('panel-result').innerHTML = `<div class="result-box result-error">Request failed: ${err}</div>`;
  });
});

// --- Render prediction result with icon, confidence bar, before/after toggle ---
function renderResult(result) {
  const container = document.getElementById('panel-result');

  if (result.error) {
    container.innerHTML = `<div class="result-box result-error">${result.error}</div>`;
    return;
  }
  if (result.not_modeled) {
    container.innerHTML = `<div class="result-box result-no_change">${result.message}</div>`;
    return;
  }

  const effect = result.predicted_effect;
  const icons = { increase: '⬆️', decrease: '⬇️', no_change: '➡️' };
  const words = { increase: 'INCREASE', decrease: 'DECREASE', no_change: 'NO MEANINGFUL CHANGE' };
  const changeNum = result.estimated_change;
  const sign = changeNum > 0 ? '+' : '';
  const confPct = Math.round(result.confidence * 100);

  container.innerHTML = `
    <div class="result-box result-${effect}">
      <div class="result-headline">${icons[effect]} Conflicts likely to ${words[effect]}</div>
      <div class="result-detail">
        Estimated change: ${sign}${changeNum} conflicts<br>
        Baseline: ${result.baseline_conflicts} &rarr; Predicted: ~${result.predicted_conflicts_after}
      </div>
      <div class="confidence-wrap">
        <div class="confidence-label">Confidence: ${confPct}%</div>
        <div class="confidence-track"><div class="confidence-fill" style="width:${confPct}%"></div></div>
      </div>
      ${effect !== 'no_change' ? `
        <label class="toggle-row">
          <input type="checkbox" id="before-after-toggle"/>
          <span>Preview predicted risk on map</span>
        </label>
      ` : ''}
    </div>
  `;

  const toggle = document.getElementById('before-after-toggle');
  if (toggle) {
    toggle.addEventListener('change', (e) => togglePredictedColor(e.target.checked));
  }
}

function togglePredictedColor(showPredicted) {
  const entry = markersByNodeId[selectedNodeId];
  if (!entry || !currentPredictionResult) return;

  const originalColor = TIER_COLORS[currentNodeData.severity_tier];
  const predictedColor = currentPredictionResult.predicted_effect === 'decrease' ? '#22c55e' : '#ef4444';

  entry.marker.setStyle({
    color: showPredicted ? predictedColor : originalColor,
    fillColor: showPredicted ? predictedColor : originalColor
  });
}

// --- Intro modal ---
window.addEventListener('load', () => {
  if (!localStorage.getItem('surakshapath_intro_seen')) {
    document.getElementById('intro-overlay').classList.add('visible');
  }
});
document.getElementById('intro-close-btn').addEventListener('click', () => {
  document.getElementById('intro-overlay').classList.remove('visible');
  localStorage.setItem('surakshapath_intro_seen', '1');
});