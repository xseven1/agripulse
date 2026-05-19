const messagesEl = document.getElementById('chat-messages');
const inputEl = document.getElementById('chat-input');
const sendBtn = document.getElementById('chat-send');

let currentModule = 'slaughter';
let currentContext = {};
let history = [];

async function fetchModuleContext(module) {
  try {
    const res = await fetch(`/api/insight/${module}/`);
    const data = await res.json();
    return { module, insight: data.insight || '', as_of: new Date().toISOString() };
  } catch {
    return { module };
  }
}

function appendMessage(role, text) {
  const wrap = document.createElement('div');
  wrap.className = `chat-msg chat-msg--${role === 'user' ? 'user' : 'ai'}`;
  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = role === 'user' ? 'You' : 'AgriPulse AI';
  const body = document.createElement('div');
  body.className = 'msg-body';
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
  body.innerHTML = '<span class="spinner"></span> Analyzing market data...';
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
        history: history.slice(-8),
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
