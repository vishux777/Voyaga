/* ═══════════════════════════════════════════
   VOYAGA — Main Application JS
═══════════════════════════════════════════ */

const BASE_URL = '';

// ── AUTH ──────────────────────────────────
function getToken() { return localStorage.getItem('voyaga_access'); }
function getUser() { return JSON.parse(localStorage.getItem('voyaga_user') || 'null'); }

function setAuth(data) {
  localStorage.setItem('voyaga_access', data.tokens.access);
  localStorage.setItem('voyaga_refresh', data.tokens.refresh);
  localStorage.setItem('voyaga_user', JSON.stringify(data.user));
  updateNavUI(data.user);
}

function logout() {
  localStorage.removeItem('voyaga_access');
  localStorage.removeItem('voyaga_refresh');
  localStorage.removeItem('voyaga_user');
  updateNavUI(null);
  showToast('Signed out successfully', 'success');
  window.location.href = '/';
}

function updateNavUI(user) {
  const actions = document.getElementById('navActions');
  const navUser = document.getElementById('navUser');
  if (!actions || !navUser) return;
  if (user) {
    actions.classList.add('hidden');
    navUser.classList.remove('hidden');
    document.getElementById('userAvatar').textContent = (user.first_name?.[0] || user.email[0]).toUpperCase();
    loadNotifications();
  } else {
    actions.classList.remove('hidden');
    navUser.classList.add('hidden');
  }
}

// ── API ───────────────────────────────────
async function api(url, method = 'GET', body = null, silent = false) {
  const headers = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (token) headers['Authorization'] = 'Bearer ' + token;

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  try {
    const res = await fetch(BASE_URL + url, opts);

    if (res.status === 401) {
      const refreshed = await tryRefresh();
      if (refreshed) return api(url, method, body, silent);
      if (getToken()) logout();
      return null;
    }

    const text = await res.text();
    if (!text) return res.ok ? {} : null;

    let data;
    try { data = JSON.parse(text); }
    catch { if (!res.ok && !silent) showToast('Server error. Please try again.', 'error'); return null; }

    if (!res.ok) {
      if (!silent) showToast(extractError(data), 'error');
      return null;
    }
    return data;
  } catch (err) {
    if (!silent && method !== 'GET') {
      showToast('Cannot connect to server. Is Django running?', 'error');
    }
    return null;
  }
}

async function tryRefresh() {
  const refresh = localStorage.getItem('voyaga_refresh');
  if (!refresh) return false;
  try {
    const res = await fetch(BASE_URL + '/api/auth/token/refresh/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh })
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem('voyaga_access', data.access);
    return true;
  } catch { return false; }
}

function extractError(data) {
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;
  if (data.non_field_errors) return data.non_field_errors[0];
  const keys = Object.keys(data);
  if (keys.length) {
    const val = data[keys[0]];
    return Array.isArray(val) ? `${keys[0]}: ${val[0]}` : String(val);
  }
  return 'An error occurred';
}

// ── MODALS ────────────────────────────────
function showModal(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove('hidden');
  const inner = el.querySelector('.modal');
  if (inner) {
    inner.style.opacity = '0';
    inner.style.transform = 'translateY(-16px) scale(0.97)';
    requestAnimationFrame(() => {
      inner.style.transition = 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)';
      inner.style.opacity = '1';
      inner.style.transform = 'translateY(0) scale(1)';
    });
  }
}

function hideModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('hidden');
}

function switchModal(from, to) { hideModal(from); showModal(to); }

document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) hideModal(e.target.id);
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') document.querySelectorAll('.modal-overlay').forEach(m => m.classList.add('hidden'));
});

// ── AUTH FORMS ────────────────────────────
async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('loginBtn');
  const errEl = document.getElementById('loginError');
  btn.textContent = 'Signing in...'; btn.disabled = true;
  errEl.classList.add('hidden');

  const result = await api('/api/auth/login/', 'POST', {
    email: document.getElementById('loginEmail').value,
    password: document.getElementById('loginPassword').value
  });

  btn.textContent = 'Sign In'; btn.disabled = false;

  if (result) {
    setAuth(result);
    hideModal('loginModal');
    showToast(`Welcome back, ${result.user.first_name || result.user.username}! 👋`, 'success');
    document.getElementById('loginForm').reset();
    if (typeof loadRecommended === 'function') loadRecommended();
    if (typeof loadProperties === 'function') loadProperties();
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const btn = document.getElementById('registerBtn');
  const errEl = document.getElementById('registerError');
  const succEl = document.getElementById('registerSuccess');
  btn.textContent = 'Creating account...'; btn.disabled = true;
  errEl.classList.add('hidden'); succEl.classList.add('hidden');

  const result = await api('/api/auth/register/', 'POST', {
    email: document.getElementById('regEmail').value,
    username: document.getElementById('regUsername').value,
    first_name: document.getElementById('regFirst').value,
    last_name: document.getElementById('regLast').value,
    role: document.getElementById('regRole').value,
    password: document.getElementById('regPassword').value,
    password2: document.getElementById('regPassword2').value
  });

  btn.textContent = 'Create Account'; btn.disabled = false;

  if (result) {
    setAuth(result);
    succEl.textContent = '✓ Account created! Welcome to Voyaga.';
    succEl.classList.remove('hidden');
    setTimeout(() => {
      hideModal('registerModal');
      showToast('Welcome to Voyaga! 🎉', 'success');
      document.getElementById('registerForm').reset();
    }, 1500);
  }
}

// ── TOAST ─────────────────────────────────
let toastTimer;
function showToast(msg, type = '') {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.className = 'toast' + (type ? ' ' + type : '');
  toast.classList.remove('hidden');
  toast.style.transition = 'none';
  toast.style.transform = 'translateY(20px)';
  toast.style.opacity = '0';
  requestAnimationFrame(() => {
    toast.style.transition = 'all 0.3s ease';
    toast.style.transform = 'translateY(0)';
    toast.style.opacity = '1';
  });
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.classList.add('hidden'), 300);
  }, 3500);
}

// ── PROPERTY CARDS ────────────────────────
function propertyCard(p) {
  const img = p.primary_image_url
    ? `<img src="${p.primary_image_url}" alt="${p.title}" loading="lazy">`
    : `<div class="card-no-img">🏠</div>`;
  const stars = p.avg_rating ? `★ ${p.avg_rating}` : '✦ New';
  return `
    <div class="property-card" onclick="window.location.href='/property/${p.id}'">
      <div class="card-image">
        ${img}
        <div class="card-type-badge">${p.property_type}</div>
      </div>
      <div class="card-body">
        <div class="card-location">📍 ${p.city}, ${p.country}</div>
        <div class="card-title">${p.title}</div>
        <div class="card-specs">
          <span>👥 ${p.max_guests}</span>
          <span>🛏 ${p.bedrooms}bd</span>
          <span>🚿 ${p.bathrooms}ba</span>
        </div>
        <div class="card-footer">
          <div class="card-price">$${parseFloat(p.price_per_night).toFixed(0)}<span class="card-price-night">/night</span></div>
          <div class="card-rating">${stars}</div>
        </div>
      </div>
    </div>`;
}

// ── NOTIFICATIONS ─────────────────────────
let notifOpen = false;

async function loadNotifications() {
  if (!getToken()) return;
  const data = await api('/api/auth/notifications/', 'GET', null, true);
  if (!data) return;

  const badge = document.getElementById('notifBadge');
  const list = document.getElementById('notifList');
  if (!badge || !list) return;

  if (data.unread > 0) {
    badge.textContent = data.unread > 9 ? '9+' : data.unread;
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }

  if (!data.results || data.results.length === 0) {
    list.innerHTML = '<div class="notif-empty">No notifications yet 🔔</div>';
    return;
  }

  list.innerHTML = data.results.map(n => `
    <div class="notif-item ${n.is_read ? '' : 'unread'}" onclick="handleNotifClick(${n.id}, '${n.link}')">
      <div class="notif-item-title">${n.title}</div>
      <div class="notif-item-msg">${n.message}</div>
      <div class="notif-item-time">${timeAgo(n.created_at)}</div>
    </div>`).join('');
}

function toggleNotifications() {
  const dropdown = document.getElementById('notifDropdown');
  if (!dropdown) return;
  notifOpen = !notifOpen;
  dropdown.classList.toggle('hidden', !notifOpen);
  if (notifOpen) loadNotifications();
}

async function markAllRead(e) {
  e.stopPropagation();
  await api('/api/auth/notifications/', 'POST', {}, true);
  loadNotifications();
}

async function handleNotifClick(id, link) {
  await api(`/api/auth/notifications/${id}/read/`, 'POST', {}, true);
  if (link) window.location.href = link;
  else toggleNotifications();
}

function timeAgo(iso) {
  const diff = (Date.now() - new Date(iso)) / 1000;
  if (diff < 60) return 'Just now';
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

// Close notifications when clicking outside
document.addEventListener('click', function(e) {
  const bell = document.getElementById('notifBell');
  const dropdown = document.getElementById('notifDropdown');
  if (notifOpen && bell && !bell.contains(e.target)) {
    notifOpen = false;
    if (dropdown) dropdown.classList.add('hidden');
  }
});

// ── AI CHAT ───────────────────────────────
let chatHistory = [];
let isTyping = false;

function toggleChat() {
  const panel = document.getElementById('chatPanel');
  const isHidden = panel.classList.contains('hidden');
  if (isHidden) {
    panel.classList.remove('hidden');
    panel.style.transition = 'none';
    panel.style.opacity = '0';
    panel.style.transform = 'translateY(24px) scale(0.96)';
    requestAnimationFrame(() => {
      panel.style.transition = 'all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1)';
      panel.style.opacity = '1';
      panel.style.transform = 'translateY(0) scale(1)';
    });
    setTimeout(() => document.getElementById('chatInput')?.focus(), 350);
  } else {
    panel.style.transition = 'all 0.22s ease';
    panel.style.opacity = '0';
    panel.style.transform = 'translateY(16px) scale(0.96)';
    setTimeout(() => panel.classList.add('hidden'), 220);
  }
}

function quickChat(msg) {
  if (isTyping) return;
  document.getElementById('chatInput').value = msg;
  sendChat();
}

async function sendChat() {
  if (isTyping) return;
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';

  appendMsg(msg, 'user');

  if (!getToken()) {
    await typingDelay(700);
    await typeMessage("Please sign in to chat with Voya AI! Click Sign in in the top right. 👋");
    return;
  }

  chatHistory.push({ role: 'user', content: msg });
  showThinking(true);

  const [result] = await Promise.all([
    api('/api/auth/chat/', 'POST', { message: msg, history: chatHistory }),
    typingDelay(1000 + Math.random() * 700)
  ]);

  showThinking(false);

  if (result?.reply) {
    await typeMessage(result.reply);
    chatHistory.push({ role: 'assistant', content: result.reply });
    if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);
  } else {
    await typeMessage("Sorry, I had a little trouble there. Give me a moment and try again! 🙏");
  }
}

function typingDelay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function formatBubble(text) {
  return escapeHtml(text)
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
}

async function typeMessage(text) {
  isTyping = true;
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'chat-msg ai';
  div.style.opacity = '0';
  div.style.transform = 'translateY(10px)';
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  div.appendChild(bubble);
  container.appendChild(div);
  requestAnimationFrame(() => {
    div.style.transition = 'all 0.28s ease';
    div.style.opacity = '1';
    div.style.transform = 'translateY(0)';
  });

  const cursor = document.createElement('span');
  cursor.className = 'typing-cursor';
  cursor.textContent = '|';

  let displayed = '';
  for (let i = 0; i < text.length; i++) {
    displayed += text[i];
    bubble.innerHTML = formatBubble(displayed);
    bubble.appendChild(cursor);
    container.scrollTop = container.scrollHeight;
    const ch = text[i];
    let delay = ch === '.' || ch === '!' || ch === '?' ? 52 : ch === ',' ? 28 : ch === ' ' ? 7 : 12 + Math.random() * 7;
    await typingDelay(delay);
  }
  bubble.innerHTML = formatBubble(text);
  container.scrollTop = container.scrollHeight;
  isTyping = false;
}

function appendMsg(text, role) {
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  div.style.opacity = '0';
  div.style.transform = 'translateY(10px)';
  div.innerHTML = `<div class="msg-bubble">${escapeHtml(text)}</div>`;
  container.appendChild(div);
  requestAnimationFrame(() => {
    div.style.transition = 'all 0.25s ease';
    div.style.opacity = '1';
    div.style.transform = 'translateY(0)';
  });
  container.scrollTop = container.scrollHeight;
}

function showThinking(show) {
  const el = document.getElementById('thinkingIndicator');
  if (!el) return;
  if (show) {
    el.classList.remove('hidden');
    el.style.opacity = '0';
    requestAnimationFrame(() => { el.style.transition = 'opacity 0.3s ease'; el.style.opacity = '1'; });
  } else {
    el.style.opacity = '0';
    setTimeout(() => el.classList.add('hidden'), 300);
  }
}

// ── NAVBAR SCROLL ─────────────────────────
window.addEventListener('scroll', () => {
  const nav = document.getElementById('navbar');
  if (nav) nav.classList.toggle('scrolled', window.scrollY > 50);
});

// ── DROPDOWN ──────────────────────────────
function toggleDropdown() {
  const dd = document.getElementById('userDropdown');
  if (!dd) return;
  const isOpen = dd.classList.contains('open');
  if (!isOpen) {
    dd.classList.add('open');
    dd.style.transition = 'none';
    dd.style.opacity = '0';
    dd.style.transform = 'translateY(-10px) scale(0.96)';
    requestAnimationFrame(() => {
      dd.style.transition = 'all 0.22s cubic-bezier(0.34, 1.56, 0.64, 1)';
      dd.style.opacity = '1';
      dd.style.transform = 'translateY(0) scale(1)';
    });
  } else {
    dd.style.transition = 'all 0.16s ease';
    dd.style.opacity = '0';
    dd.style.transform = 'translateY(-8px) scale(0.96)';
    setTimeout(() => dd.classList.remove('open'), 160);
  }
}

document.addEventListener('click', function(e) {
  const menu = document.getElementById('userMenuBtn');
  const dd = document.getElementById('userDropdown');
  if (dd && menu && !menu.contains(e.target) && dd.classList.contains('open')) {
    dd.style.transition = 'all 0.16s ease';
    dd.style.opacity = '0';
    dd.style.transform = 'translateY(-8px) scale(0.96)';
    setTimeout(() => dd.classList.remove('open'), 160);
  }
});

// ── TYPING CURSOR CSS ─────────────────────
const _cursorStyle = document.createElement('style');
_cursorStyle.textContent = `
  .typing-cursor { display:inline-block; width:1.5px; height:0.9em; background:currentColor; margin-left:1px; vertical-align:middle; opacity:0.8; animation:_vcursor 0.65s step-end infinite; }
  @keyframes _vcursor { 0%,100%{opacity:0.8} 50%{opacity:0} }
`;
document.head.appendChild(_cursorStyle);

// ── INIT ──────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const user = getUser();
  updateNavUI(user);

  // Poll notifications every 60 seconds
  if (user) {
    setInterval(loadNotifications, 60000);
  }
});