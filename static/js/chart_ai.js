// Per-chart AI insight + ask functionality
// Usage: initChartAI('chart_id') on each chart card

const _chartHistories = {};

function initChartAI(chartId) {
  _chartHistories[chartId] = [];
}

function loadChartInsight(chartId) {
  const el = document.getElementById(`insight-${chartId}`);
  const btn = document.getElementById(`btn-insight-${chartId}`);
  if (!el || !btn) return;

  btn.textContent = 'Loading…';
  btn.disabled = true;

  fetch(`/api/chart-insight/${chartId}/`)
    .then(r => r.json())
    .then(data => {
      if (data.insight) {
        el.textContent = data.insight;
        el.classList.add('loaded');
      } else {
        el.textContent = 'Insight unavailable.';
      }
      btn.textContent = '↻ Refresh';
      btn.disabled = false;
    })
    .catch(() => {
      el.textContent = 'Could not load insight.';
      btn.textContent = 'AI Insight';
      btn.disabled = false;
    });
}

function toggleAskPanel(chartId) {
  const panel = document.getElementById(`ask-panel-${chartId}`);
  if (!panel) return;
  panel.classList.toggle('open');
  if (panel.classList.contains('open')) {
    document.getElementById(`ask-input-${chartId}`)?.focus();
  }
}

function askChart(chartId) {
  const input = document.getElementById(`ask-input-${chartId}`);
  const history_el = document.getElementById(`ask-history-${chartId}`);
  const btn = document.getElementById(`ask-send-${chartId}`);
  if (!input || !history_el || !btn) return;

  const question = input.value.trim();
  if (!question) return;

  input.value = '';
  btn.disabled = true;

  // Add user message
  const userMsg = document.createElement('div');
  userMsg.className = 'ask-msg user';
  userMsg.textContent = question;
  history_el.appendChild(userMsg);

  // Add loading
  const loadMsg = document.createElement('div');
  loadMsg.className = 'ask-msg ai loading';
  loadMsg.textContent = 'Analyzing…';
  history_el.appendChild(loadMsg);
  history_el.scrollTop = history_el.scrollHeight;

  _chartHistories[chartId] = _chartHistories[chartId] || [];
  _chartHistories[chartId].push({ role: 'user', content: question });

  fetch(`/api/chart-ask/${chartId}/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question: question,
      history: _chartHistories[chartId].slice(-6),
    }),
  })
    .then(r => r.json())
    .then(data => {
      loadMsg.remove();
      const aiMsg = document.createElement('div');
      aiMsg.className = 'ask-msg ai';
      aiMsg.textContent = data.response || data.error || 'No response.';
      history_el.appendChild(aiMsg);
      history_el.scrollTop = history_el.scrollHeight;
      if (data.response) {
        _chartHistories[chartId].push({ role: 'assistant', content: data.response });
      }
      btn.disabled = false;
      input.focus();
    })
    .catch(() => {
      loadMsg.textContent = 'Connection error.';
      loadMsg.classList.remove('loading');
      btn.disabled = false;
    });
}

// Enter key support for ask inputs
document.addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && e.target.classList.contains('chart-ask-input')) {
    e.preventDefault();
    const chartId = e.target.dataset.chartId;
    if (chartId) askChart(chartId);
  }
});
