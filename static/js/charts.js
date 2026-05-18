function renderChart(id, dataJson) {
  const el = document.getElementById(id);
  if (!el) return;
  let data;
  try { data = typeof dataJson === 'string' ? JSON.parse(dataJson) : dataJson; }
  catch(e) { el.innerHTML = '<p style="color:#5A6077;padding:1rem;font-size:.8rem;">Chart data error</p>'; return; }
  const { data: traces, layout } = data;

  // Light theme overrides
  layout.paper_bgcolor = 'rgba(0,0,0,0)';
  layout.plot_bgcolor  = '#FFFFFF';
  layout.font = { color: '#1A1D2E', family: 'DM Sans, sans-serif', size: 11 };
  layout.margin = layout.margin || { l: 10, r: 10, t: 14, b: 10 };

  // Light grid
  if (layout.xaxis) {
    layout.xaxis.gridcolor = '#EEF0F5';
    layout.xaxis.tickfont = { color: '#5A6077', size: 10 };
    layout.xaxis.linecolor = '#E2E6EE';
  }
  if (layout.yaxis) {
    layout.yaxis.gridcolor = '#EEF0F5';
    layout.yaxis.tickfont = { color: '#5A6077', size: 10 };
  }

  // Legend
  if (layout.legend) {
    layout.legend.bgcolor = 'rgba(255,255,255,0.9)';
    layout.legend.bordercolor = '#E2E6EE';
    layout.legend.font = { color: '#1A1D2E', size: 10 };
  }

  // Hover
  layout.hoverlabel = {
    bgcolor: '#FFFFFF',
    bordercolor: '#E2E6EE',
    font: { color: '#1A1D2E', size: 11 },
  };

  Plotly.newPlot(el, traces, layout, { responsive: true, displayModeBar: false });
}

function renderAllCharts(chartMap) {
  Object.entries(chartMap).forEach(([id, json]) => renderChart(id, json));
}