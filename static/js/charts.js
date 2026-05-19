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


// ── PERIOD TOGGLE ──────────────────────────────────────────────────────────────

const _chartPeriodCache = {};

function initPeriodToggle(chartId, module) {
  // Store module for API calls
  _chartPeriodCache[chartId] = { module, current: 'year' };
}

async function switchPeriod(chartId, period, btn) {
  // Update button states
  const bar = btn.closest('.period-bar');
  if (bar) bar.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  const cache = _chartPeriodCache[chartId];
  if (!cache) return;
  if (cache.current === period) return;
  cache.current = period;

  const el = document.getElementById(chartId);
  if (!el) return;

  // Show loading state
  el.style.opacity = '0.5';

  try {
    const res = await fetch(`/api/chart-period/${chartId}/?period=${period}&module=${cache.module}`);
    const data = await res.json();
    if (data.chart) {
      renderChart(chartId, data.chart);
    }
  } catch (e) {
    console.error('Period switch failed:', e);
  } finally {
    el.style.opacity = '1';
  }
}
