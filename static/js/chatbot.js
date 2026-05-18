const messagesEl = document.getElementById('chat-messages');
const inputEl = document.getElementById('chat-input');
const sendBtn = document.getElementById('chat-send');
const moduleButtons = document.querySelectorAll('.filter-btn[data-module]');

let currentModule = 'general';
let currentContext = {};
let history = [];

async function fetchModuleContext(module) {
  if (module === 'general') return {};
  try {
    const res = await fetch(`/api/insights/${module}/`);
    const data = await res.json();
    return { insight: data.insight || '' };
  } catch {
    return {};
  }
}

moduleButtons.forEach(btn => {
  btn.addEventListener('click', async () => {
    moduleButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentModule = btn.dataset.module;
    currentContext = await fetchModuleContext(currentModule);
  });
});

function appendMessage(role, text) {
  const wrap = document.createElement('div');
  wrap.className = `chat-msg chat-msg--${role === 'user' ? 'user' : 'ai'}`;

  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = role === 'user' ? 'You' : 'AgriPulse AI';

  const body = document.createElement('div');
  body.className = 'msg-body';
  // Render newlines properly
  body.innerHTML = text.replace(/\n/g, '<br>');

  wrap.appendChild(label);
  wrap.appendChild(body);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return body;
}

function appendLoading() {
  const wrap = document.createElement('div');
  wrap.className = 'chat-msg chat-msg--ai chat-msg--loading';
  wrap.id = 'loading-msg';
  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = 'AgriPulse AI';
  const body = document.createElement('div');
  body.className = 'msg-body';
  body.textContent = 'Analyzing market data…';
  wrap.appendChild(label);
  wrap.appendChild(body);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function removeLoading() {
  const el = document.getElementById('loading-msg');
  if (el) el.remove();
}

async function sendMessage() {
  const message = inputEl.value.trim();
  if (!message) return;

  inputEl.value = '';
  sendBtn.disabled = true;
  appendMessage('user', message);
  appendLoading();

  history.push({ role: 'user', content: message });

  // If no context loaded yet for current module, fetch it now
  if (currentModule !== 'general' && Object.keys(currentContext).length === 0) {
    currentContext = await fetchModuleContext(currentModule);
  }

  try {
    const res = await fetch('/api/chat/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        module: currentModule,
        context: currentContext,
        history: history.slice(-6),
      }),
    });

    const data = await res.json();
    removeLoading();

    if (data.error) {
      appendMessage('ai', `Error: ${data.error}`);
    } else {
      appendMessage('ai', data.response);
      history.push({ role: 'assistant', content: data.response });
    }
  } catch (err) {
    removeLoading();
    appendMessage('ai', `Connection error: ${err.message}`);
  }

  sendBtn.disabled = false;
  inputEl.focus();
}

sendBtn.addEventListener('click', sendMessage);
inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Auto-select module from URL param and load context
(async () => {
  const urlParams = new URLSearchParams(window.location.search);
  const moduleParam = urlParams.get('module');
  if (moduleParam) {
    moduleButtons.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.module === moduleParam);
    });
    currentModule = moduleParam;
    currentContext = await fetchModuleContext(moduleParam);
  }
})();
