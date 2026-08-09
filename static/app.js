const map = L.map('map', { zoomControl: true }).setView([22.5726, 88.3639], 15);

L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
  maxZoom: 19
}).addTo(map);

let selectedNodeId = null;
let markers = {};

fetch('/api/heatmap')
  .then(res => res.json())
  .then(data => {
    const maxConflict = Math.max(...data.map(d => d[2]));
    const heatPoints = data.map(d => [d[0], d[1], d[2]]);

    L.heatLayer(heatPoints, {
      radius: 18,
      blur: 14,
      maxZoom: 17,
      max: maxConflict,
      gradient: {
        0.0: '#1e3a8a',   // deep blue - very low
        0.25: '#3b82f6',  // blue - low
        0.45: '#22c55e',  // green - moderate-low
        0.6: '#eab308',   // yellow - moderate
        0.75: '#f97316',  // orange - high
        1.0: '#ef4444'    // red - very high
      }
    }).addTo(map);
  });

fetch('/api/nodes')
  .then(res => res.json())
  .then(nodes => {
    nodes.forEach(node => {
      const color = node.total_conflicts > 150 ? '#f85149' : node.total_conflicts > 60 ? '#f0883e' : '#3fb950';
      const marker = L.circleMarker([node.lat, node.lon], {
        radius: 9, color: color, fillColor: color, fillOpacity: 0.85, weight: 2
      }).addTo(map);

      marker.on('click', () => openPanel(node));
      markers[node.node_id] = marker;
    });
  });

function openPanel(node) {
  selectedNodeId = node.node_id;
  document.getElementById('panel').classList.remove('hidden');
  document.getElementById('panel-title').innerText = node.node_id;
  document.getElementById('panel-stats').innerHTML = `
    <div><span class="label">Baseline conflicts:</span> ${node.total_conflicts}</div>
    <div><span class="label">Severe conflicts:</span> ${node.severe_conflicts}</div>
    <div><span class="label">Has signal:</span> ${node.has_signal ? 'Yes' : 'No'}</div>
  `;
  document.getElementById('panel-result').innerHTML = '';

  const select = document.getElementById('intervention-select');
  select.querySelector('option[value="signal_retiming"]').disabled = !node.has_signal;
  if (!node.has_signal) select.value = 'speed_breaker';
}

document.getElementById('panel-close').addEventListener('click', () => {
  document.getElementById('panel').classList.add('hidden');
});

document.getElementById('intervention-select').addEventListener('change', (e) => {
  document.getElementById('other-input-wrap').classList.toggle('hidden', e.target.value !== 'other');
});

document.getElementById('add-intervention-btn').addEventListener('click', () => {
  const intervention = document.getElementById('intervention-select').value;
  const btn = document.getElementById('add-intervention-btn');
  btn.disabled = true;
  btn.innerText = 'Predicting...';

  fetch('/api/predict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_id: selectedNodeId, intervention: intervention })
  })
  .then(res => res.json())
  .then(result => {
    btn.disabled = false;
    btn.innerText = 'Add Intervention';
    renderResult(result);
  })
  .catch(err => {
    btn.disabled = false;
    btn.innerText = 'Add Intervention';
    document.getElementById('panel-result').innerHTML = `<div class="result-box result-error">Request failed: ${err}</div>`;
  });
});

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
  const changeWord = effect === 'increase' ? 'INCREASE' : effect === 'decrease' ? 'DECREASE' : 'NO MEANINGFUL CHANGE';
  const changeNum = result.estimated_change;
  const sign = changeNum > 0 ? '+' : '';

  container.innerHTML = `
    <div class="result-box result-${effect}">
      <div class="result-headline">Conflicts likely to ${changeWord}</div>
      <div class="result-detail">
        Estimated change: ${sign}${changeNum} conflicts<br>
        Baseline: ${result.baseline_conflicts} &rarr; Predicted: ~${result.predicted_conflicts_after}<br>
        Confidence: ${(result.confidence * 100).toFixed(0)}%
      </div>
    </div>
  `;
}