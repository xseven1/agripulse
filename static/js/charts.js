function renderChart(id, dataJson) {
  const el = document.getElementById(id);
  if (!el) return;
  let data;
  try { data = typeof dataJson === 'string' ? JSON.parse(dataJson) : dataJson; }
  catch(e) { el.innerHTML = '<p style="color:#A0AEC0;padding:1rem;font-size:.8rem;">Chart data error</p>'; return; }
  const { data: traces, layout } = data;
  layout.paper_bgcolor = 'rgba(0,0,0,0)';
  layout.plot_bgcolor  = '#111827';
  layout.font = { color: '#FFFFFF', family: 'DM Sans, sans-serif', size: 11 };
  layout.margin = layout.margin || { l: 8, r: 8, t: 12, b: 8 };
  Plotly.newPlot(el, traces, layout, { responsive: true, displayModeBar: false });
}

function renderAllCharts(chartMap) {
  Object.entries(chartMap).forEach(([id, json]) => renderChart(id, json));
}
